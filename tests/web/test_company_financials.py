"""The company page's Financials tab (the Financials tab's design, 7.1 to 7.4, 7.7, 7.8 and 7.9;
Review Focus 2, 3 and 5): its place in the tabs' row and in the hash, its controls by sub-tab, the
tables of each sub-tab with their rows' kinds, the captions, a column's head, a figure's text, an
empty table's sentence, the unit kept in the browser, and the lines on the chart, a row's button
that adds one or takes it off and the colour each keeps. company.js and company_financials.js run
in node after the bundle and app.js (``support.page``), and the tests read what the tab's
functions return and the trees its builder draws; ``financials.mjs`` drives the tab's state, with
a store of its own, and with the chart's scripts where a test reads the picks the tab hands its
chart; the layout node cannot run is read from the page's CSS.

The answer is made here, ``ANSWER``, ACME's, in US dollars: two fiscal years and two quarters of
each statement, a revenue by product and by region, and a table of ratios. Its 2025 column of the
balance sheet names euros."""

import copy
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support import page_answers as answers
from support.page import BUNDLE, NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (STATIC / "company.js", STATIC / "company_financials.js")
CHARTED = (  # the tab with its chart, whose place then holds the picks
    STATIC / "company.js",
    STATIC / "company_chart.js",
    STATIC / "company_financials.js",
    STATIC / "company_financials_chart.js",
)
DRIVER = Path(__file__).parent / "financials.mjs"
KEY = "fairband.financials.unit"
SUBTABS = ["Income statement", "Balance sheet", "Cash flow", "Segments", "Ratios"]
RIGHT = "press a line to chart it alone, or its + to add it to the chart"
DASH = "—"
ADD = "Add to the chart"
TAKE = "Take off the chart"
FULL = "The chart holds 4 lines. Take one off first."


def _row(key: str, label: str, kind: str, unit: str, values: list[Any]) -> dict[str, Any]:
    """A line of a table as the read gives it, named on the chart as in the table."""
    return {"key": key, "label": label, "name": label, "kind": kind, "unit": unit, "values": values}


def _head(label: str) -> dict[str, Any]:
    """A section head as the read gives it: its label, no key, name, unit or values."""
    return {"key": None, "label": label, "name": None, "kind": "head", "unit": None, "values": None}


def _years(first: str = "USD") -> list[dict[str, Any]]:
    """The two fiscal years, oldest first, the first in ``first``."""
    return [
        {"label": "2025", "end": "2025-09-30", "currency": first},
        {"label": "2026", "end": "2026-09-30", "currency": "USD"},
    ]


QUARTERS = [
    {"label": "Q3 2026", "end": "2026-06-30", "currency": "USD"},
    {"label": "Q4 2026", "end": "2026-09-30", "currency": "USD"},
]

INCOME = {
    "columns": _years(),
    "rows": [
        _row("revenue", "Revenue", "total", "money", [61_200e6, 72_480e6]),
        _row("costOfRevenue", "Cost of revenue", "line", "money", [-33_150e6, -38_010e6]),
        _row("grossProfit", "Gross profit", "total", "money", [28_050e6, 34_470e6]),
        _row(
            "generalAndAdministrativeExpenses",
            "General and administrative",
            "sub",
            "money",
            [4_120e6, None],
        ),
        _row("eps", "EPS", "line", "perShare", [2.104, 2.716]),
        _row("weightedAverageShsOut", "Shares, basic", "line", "shares", [5_210e6, 5_102e6]),
    ],
}
INCOME_QUARTERS = {
    "columns": QUARTERS,
    "rows": [_row("revenue", "Revenue", "total", "money", [17_390e6, 19_020e6])],
}
BALANCE = {
    "columns": _years("EUR"),
    "rows": [
        _head("ASSETS"),
        _row("cashAndCashEquivalents", "Cash", "line", "money", [8_410e6, 0]),
        _row("totalAssets", "Total assets", "total", "money", [96_300e6, 104_750e6]),
    ],
}
PRODUCT = {
    "columns": _years(),
    "rows": [
        _row("Anvils", "Anvils", "line", "money", [40_100e6, 47_900e6]),
        _row("Rockets", "Rockets", "line", "money", [21_100e6, 24_580e6]),
    ],
}
REGION = {
    "columns": _years(),
    "rows": [_row("Americas", "Americas", "line", "money", [35_000e6, 41_200e6])],
}
RATIOS = {
    "columns": _years(),
    "rows": [
        _head("MARGINS"),
        _row("grossProfitMargin", "Gross", "line", "percent", [0.4583, 0.4756]),
        _head("VALUATION"),
        _row("priceToEarningsRatio", "P/E", "line", "multiple", [24.81, 0]),
        _head("DIVIDENDS"),
        _row("dividendYield", "Yield", "line", "percent", [0.0051, 0.0042]),
    ],
}
EMPTY: dict[str, Any] = {"columns": [], "rows": []}

ANSWER: dict[str, Any] = {
    "symbol": "ACME",
    "dataDate": "2026-11-14",
    "quote": {"price": None, "change": None, "changePercent": None, "day": None},
    "currency": "USD",
    "cadence": "quarterly",
    "statements": {
        "income": {"annual": INCOME, "quarter": INCOME_QUARTERS},
        "balance": {"annual": BALANCE, "quarter": EMPTY},
        "cashflow": {"annual": EMPTY, "quarter": EMPTY},
    },
    "segments": {"product": PRODUCT, "region": REGION},
    "ratios": RATIOS,
}

VIEW = {"kind": "income", "period": "annual", "scale": "m"}


def _tab(helper: str, *args: Any) -> Any:
    """What ``companyFinancials.<helper>`` returns on ``args``, company.js and
    company_financials.js loaded after app.js, as the page loads them."""
    return node("companyFinancials." + helper, list(args), *SCRIPTS)


def _block(answer: dict[str, Any] = ANSWER, **view: str) -> Any:
    """The tab's block on ``answer`` at the view ``VIEW`` with ``view`` laid over it, with no
    line on the chart and no handlers (none is called while it is drawn)."""
    return _tab("block", answer, VIEW | view, [], None)


def _drive(
    store: Any, steps: list[dict[str, Any]], loaded: tuple[Path, ...] = SCRIPTS
) -> list[dict[str, Any]]:
    """The trace of ``steps`` with the store ``store`` (``financials.mjs``), the scripts
    ``loaded`` after app.js."""
    assert NODE is not None
    scripts = (BUNDLE, STATIC / "app.js", *loaded)
    done = subprocess.run(
        [NODE, str(DRIVER), *(str(script) for script in scripts)],
        input=json.dumps({"store": store, "steps": steps}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    trace: list[dict[str, Any]] = json.loads(done.stdout)
    return trace


def _press(name: str, words: str) -> dict[str, Any]:
    return {"do": "press", "class": name, "text": words}


def _typed(tree: Any, kind: str) -> list[dict[str, Any]]:
    return [e for e in elements(tree) if e.get("type") == kind]


def _words(cell: dict[str, Any]) -> str:
    """The text of a cell, a row's button before its name left out."""
    kids = cell["props"].get("children")
    return text([k for k in (kids if isinstance(kids, list) else [kids]) if not _button(k)])


def _button(tree: Any) -> bool:
    return isinstance(tree, dict) and tree.get("type") == "button"


def _grid(table: dict[str, Any]) -> list[list[str]]:
    """The texts of a drawn table: its head's cells, then each row's, its name first."""
    return [
        [_words(cell) for cell in elements(row) if cell.get("type") in ("th", "td")]
        for row in _typed(table, "tr")
    ]


def _view(view: dict[str, Any] | None) -> tuple[Any, Any, Any] | None:
    return None if view is None else (view["tab"], view["unit"], view["period"])


# ------------------------------------------------------------------------- the tab in the row


def test_the_tab_stands_second_and_its_hash_reads_both_ways() -> None:
    """The tabs' row reads Overview, Financials, Estimates, Investor relations and Research;
    Financials is a tab, selected where it is open. controls.js knows its name, so
    #company/ACME/financials opens it (tests/web/test_company_load.py drives the loader there);
    the tab's function hangs on the page's draw, keyed on the company of its answer, so another
    company's tab is a new one."""
    tree = node("companyPage.tabs", ["ACME", "financials", "2026-11-14"], *SCRIPTS)
    tabs = classed(tree, "app-company__tab")
    assert [text(t) for t in tabs] == [
        "Overview",
        "Financials",
        "Estimates",
        "Investor relations",
        "Research",
    ]
    assert [t["props"].get("aria-selected") for t in tabs] == ["false", "true"] + ["false"] * 3
    assert tabs[1]["props"]["role"] == "tab"
    js = _static_file("controls.js")
    companies = "['overview', 'financials', 'estimates', 'investor-relations', 'research']"
    assert f"\n  var COMPANY_TABS = {companies};\n" in js
    drawn = node("companyPage.draw.financials", [ANSWER, answers.DETAIL], *SCRIPTS)
    assert drawn["props"]["key"] == "ACME"
    assert drawn["props"]["symbol"] == "ACME"
    assert drawn["props"]["answer"] == ANSWER
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert scripts.index("company_financials.js") == scripts.index("company_estimates.js") + 1


# ------------------------------------------------------------------------------ the controls


def test_the_controls_by_sub_tab() -> None:
    """The row of controls: the five sub-tabs, the open one selected; Millions and Billions on
    every sub-tab but Ratios; Annual and Quarterly on the three statements, Half-yearly in
    Quarterly's place for a company that reports twice a year. A yearly sub-tab sets the period
    to Annual. The panel holds, in order, the controls, the chart's place, the captions and the
    table."""
    assert _tab("step", VIEW | {"period": "quarter"}, {"kind": "ratios"}) == {
        "kind": "ratios",
        "period": "annual",
        "scale": "m",
    }
    assert _tab("step", VIEW, {"kind": "balance"}) == VIEW | {"kind": "balance"}
    assert _tab("step", VIEW, {"period": "quarter"}) == VIEW | {"period": "quarter"}
    assert _tab("step", VIEW, {"scale": "b"}) == VIEW | {"scale": "b"}
    assert _tab("yearly", "segments") is True
    assert _tab("yearly", "ratios") is True
    assert _tab("yearly", "income") is False

    tree = _block()
    assert tree["type"] == "section"
    assert tree["props"]["className"].split() == ["app-company__panel", "app-fin"]
    subtabs = classed(tree, "app-fin__tab")
    assert [text(t) for t in subtabs] == SUBTABS
    assert [t["props"]["aria-selected"] for t in subtabs] == ["true"] + ["false"] * 4
    assert {t["props"]["role"] for t in subtabs} == {"tab"}
    scales = classed(tree, "app-fin__scale")
    assert [text(b) for b in scales] == ["Millions", "Billions"]
    assert [b["props"]["aria-pressed"] for b in scales] == ["true", "false"]
    periods = classed(tree, "app-fin__period")
    assert [text(b) for b in periods] == ["Annual", "Quarterly"]
    assert [b["props"]["aria-pressed"] for b in periods] == ["true", "false"]
    groups = classed(tree, "app-fin__seg")
    assert [(g["props"]["role"], g["props"]["aria-label"]) for g in groups] == [
        ("tablist", "Statement"),
        ("group", "Unit of the amounts"),
        ("group", "Period"),
    ]
    buttons = _typed(classed(tree, "app-fin__bar")[0], "button")
    assert len(buttons) == 9
    assert {b["props"]["type"] for b in buttons} == {"button"}
    [chart] = classed(tree, "app-fin__chart")
    assert text(chart) == ""
    [table] = classed(tree, "app-fin__table")
    order = [id(e) for e in elements(tree)]
    assert order.index(id(subtabs[0])) < order.index(id(chart))
    assert order.index(id(chart)) < order.index(id(classed(tree, "app-fin__note")[0]))
    assert order.index(id(classed(tree, "app-fin__note")[1])) < order.index(id(table))

    billions = _block(scale="b", period="quarter")
    assert [b["props"]["aria-pressed"] for b in classed(billions, "app-fin__scale")] == [
        "false",
        "true",
    ]
    assert [b["props"]["aria-pressed"] for b in classed(billions, "app-fin__period")] == [
        "false",
        "true",
    ]
    segments = _block(kind="segments")
    assert [t["props"]["aria-selected"] for t in classed(segments, "app-fin__tab")][3] == "true"
    assert len(classed(segments, "app-fin__scale")) == 2
    assert classed(segments, "app-fin__period") == []
    ratios = _block(kind="ratios")
    assert classed(ratios, "app-fin__scale") == []
    assert classed(ratios, "app-fin__period") == []
    halves = _block(ANSWER | {"cadence": "half-yearly"})
    assert [text(b) for b in classed(halves, "app-fin__period")] == ["Annual", "Half-yearly"]


def test_a_press_changes_the_view_and_the_tab_keeps_it() -> None:
    """A press on a sub-tab, a unit or a period draws the tab at it. The sub-tab and the period
    are kept while the app is open, so another company's tab, a new one, opens where the last
    left them; the unit is kept in the browser. Opening Segments or Ratios sets the period to
    Annual, and leaving them keeps it."""
    trace = _drive(
        {},
        [
            {"do": "mount", "answer": ANSWER},
            _press("app-fin__scale", "Billions"),
            _press("app-fin__tab", "Ratios"),
            _press("app-fin__tab", "Income statement"),
            _press("app-fin__period", "Quarterly"),
            {"do": "mount", "answer": ANSWER | {"symbol": "BETA"}},
            _press("app-fin__tab", "Segments"),
            _press("app-fin__tab", "Balance sheet"),
            _press("app-fin__scale", "Millions"),
            {"do": "mount", "answer": ANSWER},
        ],
    )
    assert [step["threw"] for step in trace] == [False] * 10
    assert [_view(step["view"]) for step in trace] == [
        ("Income statement", "Millions", "Annual"),
        ("Income statement", "Billions", "Annual"),
        ("Ratios", None, None),
        ("Income statement", "Billions", "Annual"),
        ("Income statement", "Billions", "Quarterly"),
        ("Income statement", "Billions", "Quarterly"),
        ("Segments", "Billions", None),
        ("Balance sheet", "Billions", "Annual"),
        ("Balance sheet", "Millions", "Annual"),
        ("Balance sheet", "Millions", "Annual"),
    ]
    assert [step["store"] for step in trace] == [{}] + [{KEY: "b"}] * 7 + [{KEY: "m"}] * 2


# -------------------------------------------------------------------------------- the tables


def test_the_tables_of_each_sub_tab() -> None:
    """A statement's sub-tab holds its table at the period, with no title; Segments the revenue
    by product and by region, each under its title; Ratios the ratios' table."""
    assert _tab("tables", ANSWER, "income", "annual") == [
        {"id": None, "title": None, "table": INCOME}
    ]
    assert _tab("tables", ANSWER, "income", "quarter") == [
        {"id": None, "title": None, "table": INCOME_QUARTERS}
    ]
    assert _tab("tables", ANSWER, "balance", "annual") == [
        {"id": None, "title": None, "table": BALANCE}
    ]
    assert _tab("tables", ANSWER, "segments", "annual") == [
        {"id": "product", "title": "Revenue by product", "table": PRODUCT},
        {"id": "region", "title": "Revenue by region", "table": REGION},
    ]
    assert _tab("tables", ANSWER, "ratios", "annual") == [
        {"id": None, "title": None, "table": RATIOS}
    ]
    segments = _block(kind="segments")
    assert [text(t) for t in classed(segments, "app-fin__title")] == [
        "Revenue by product",
        "Revenue by region",
    ]
    assert len(classed(segments, "app-fin__table")) == 2
    assert classed(_block(), "app-fin__title") == []
    assert len(classed(_block(kind="ratios"), "app-fin__table")) == 1


def test_a_table_s_rows_and_kinds() -> None:
    """One column a period, oldest at the left, after the first column of the lines' names; a
    total's row carries is-total, a sub-line's is-sub, a section head's is-head with one cell
    across every column and no figure; each line a cell a figure."""
    [table] = classed(_block(), "app-fin__table")
    grid = _grid(table)
    assert grid == [
        ["USD, millions, except per share", "202530 Sep", "202630 Sep"],
        ["Revenue", "61,200", "72,480"],
        ["Cost of revenue", "−33,150", "−38,010"],
        ["Gross profit", "28,050", "34,470"],
        ["General and administrative", "4,120", DASH],
        ["EPS", "2.10", "2.72"],
        ["Shares, basic", "5,210", "5,102"],
    ]
    rows = _typed(table, "tr")[1:]
    assert [set(str(r["props"].get("className") or "").split()) for r in rows] == [
        {"is-total"},
        set(),
        {"is-total"},
        {"is-sub"},
        set(),
        set(),
    ]
    for row in rows:
        [name] = _typed(row, "th")
        assert name["props"]["scope"] == "row"
    [nil] = classed(table, "is-nil")
    assert text(nil) == DASH
    assert all(cell["props"]["className"].split()[0] == "figure" for cell in _typed(table, "td"))

    [balance] = classed(_block(kind="balance"), "app-fin__table")
    rows = _typed(balance, "tr")
    assert "is-head" in rows[1]["props"]["className"].split()
    [cell] = [e for e in elements(rows[1]) if e.get("type") in ("th", "td")]
    assert cell["type"] == "th"
    assert cell["props"]["colSpan"] == 3
    assert text(cell) == "ASSETS"
    assert _grid(balance)[2:] == [["Cash", "8,410", DASH], ["Total assets", "96,300", "104,750"]]

    quarters = _grid(classed(_block(period="quarter"), "app-fin__table")[0])
    assert quarters[0] == ["USD, millions, except per share", "Q3 202630 Jun", "Q4 202630 Sep"]


def test_every_sub_tab_of_a_whole_answer_draws_a_cell_a_figure() -> None:
    """The read's own answer (``page_answers.FINANCIALS``, in New Taiwan dollars): each table of
    each sub-tab at each period draws a row a line, the head's first, and as many cells in a
    line's row as its table has columns, after its name. No word names a vendor."""
    whole = answers.FINANCIALS
    for kind in ("income", "balance", "cashflow", "segments", "ratios"):
        for period in ("annual", "quarter"):
            found = _tab("tables", whole, kind, period)
            tree = _block(whole, kind=kind, period=period)
            drawn = classed(tree, "app-fin__table")
            assert len(drawn) == len(found)
            for given, table in zip(found, drawn, strict=True):
                columns = len(given["table"]["columns"])
                grid = _grid(table)
                assert len(grid) == len(given["table"]["rows"]) + 1
                for row, line in zip(grid[1:], given["table"]["rows"], strict=True):
                    assert len(row) == (1 if line["kind"] == "head" else columns + 1)
                    assert row[0] == line["label"]
            assert "FMP" not in text(tree)


def test_an_empty_table_says_so() -> None:
    """A table with no line draws one sentence in its place, and no table; a company with no
    statement, no segments and no ratios on file draws it on every sub-tab, under both of
    Segments' titles."""
    tree = _block(kind="cashflow")
    [none] = classed(tree, "app-fin__none")
    assert text(none) == "No figures on file."
    assert _typed(tree, "table") == []
    bare = answers.profile_only_financials()
    for kind in ("income", "balance", "cashflow", "ratios"):
        for period in ("annual", "quarter"):
            tree = _block(bare, kind=kind, period=period)
            assert [text(n) for n in classed(tree, "app-fin__none")] == ["No figures on file."]
            assert _typed(tree, "table") == []
            left, right = classed(tree, "app-fin__note")
            assert text(left) == (_tab("note", kind, period, "quarterly", 0) or "")
            assert text(right) == RIGHT
    segments = _block(bare, kind="segments")
    assert [text(t) for t in classed(segments, "app-fin__title")] == [
        "Revenue by product",
        "Revenue by region",
    ]
    assert [text(n) for n in classed(segments, "app-fin__none")] == ["No figures on file."] * 2


# ------------------------------------------------------------------------------- the captions


def test_the_captions() -> None:
    """The first column's head states the unit; the left caption what the table holds, the
    counts the table's own; the right caption how to pick a line."""
    for args, words in (
        (("income", "USD", "m"), "USD, millions, except per share"),
        (("income", "USD", "b"), "USD, billions, except per share"),
        (("balance", "TWD", "b"), "TWD, billions"),
        (("cashflow", "EUR", "m"), "EUR, millions"),
        (("segments", "USD", "m"), "USD, millions"),
        (("ratios", "USD", "m"), "as each row says; per share in USD"),
        (("ratios", "USD", "b"), "as each row says; per share in USD"),
        (("ratios", "TWD", "m"), "as each row says; per share in TWD"),
    ):
        assert _tab("caption", *args) == words, args
    for args, words in (
        (("income", "annual", "quarterly", 11), "the last 11 fiscal years"),
        (("cashflow", "quarter", "quarterly", 8), "the last 8 quarters"),
        (("balance", "quarter", "half-yearly", 6), "the last 6 half-years"),
        (("balance", "annual", "half-yearly", 9), "the last 9 fiscal years"),
        (("income", "quarter", "quarterly", 0), None),  # no row: the table's sentence says it
        (("income", "annual", "quarterly", 1), "the last fiscal year"),
        (("cashflow", "quarter", "quarterly", 1), "the last quarter"),
        (("balance", "quarter", "half-yearly", 1), "the last half-year"),
        (
            ("segments", "annual", "quarterly", 11),
            "by fiscal year, as the company reports its segments",
        ),
        (
            ("ratios", "annual", "half-yearly", 11),
            "by fiscal year; the same definitions as Key statistics on the Overview",
        ),
    ):
        assert _tab("note", *args) == words, args

    notes = classed(_block(), "app-fin__note")
    assert [text(n) for n in notes] == ["the last 2 fiscal years", RIGHT]
    lineless = copy.deepcopy(ANSWER)
    lineless["statements"]["income"]["annual"] = {"columns": _years(), "rows": []}
    tree = _block(lineless)
    assert [text(n) for n in classed(tree, "app-fin__note")] == ["", RIGHT]
    assert [text(n) for n in classed(tree, "app-fin__none")] == ["No figures on file."]
    assert {n["props"]["className"].split()[0] for n in notes} == {"caption"}
    quarters = classed(
        _block(ANSWER | {"cadence": "half-yearly"}, period="quarter"), "app-fin__note"
    )
    assert [text(n) for n in quarters] == ["the last 2 half-years", RIGHT]
    ratios = _block(kind="ratios")
    assert text(classed(ratios, "app-fin__note")[0]).startswith("by fiscal year; the same")
    assert _grid(classed(ratios, "app-fin__table")[0])[0][0] == "as each row says; per share in USD"
    taiwan = _block(answers.FINANCIALS, kind="balance", scale="b")
    assert _grid(classed(taiwan, "app-fin__table")[0])[0][0] == "TWD, billions"
    taiwan = _block(answers.FINANCIALS, kind="ratios")
    assert _grid(classed(taiwan, "app-fin__table")[0])[0][0] == "as each row says; per share in TWD"
    segments = _block(kind="segments", scale="b")
    assert [_grid(t)[0][0] for t in classed(segments, "app-fin__table")] == ["USD, billions"] * 2


def test_a_column_s_head() -> None:
    """A column's head: its period over the day and month its period ends; a third line, the
    code, where the column's currency is not the tab's."""
    assert _tab("head", {"label": "2026", "end": "2026-09-30", "currency": "USD"}, "USD") == [
        "2026",
        "30 Sep",
        None,
    ]
    assert _tab("head", {"label": "2019", "end": "2019-12-31", "currency": "EUR"}, "USD") == [
        "2019",
        "31 Dec",
        "EUR",
    ]
    assert _tab("head", {"label": "H2 2026", "end": "2026-12-31", "currency": "GBP"}, "GBP") == [
        "H2 2026",
        "31 Dec",
        None,
    ]
    [table] = classed(_block(kind="balance"), "app-fin__table")
    [code] = classed(table, "app-fin__code")
    assert text(code) == "EUR"
    heads = _typed(_typed(table, "thead")[0], "th")
    assert code in list(elements(heads[1]))
    assert [h["props"]["scope"] for h in heads] == ["col"] * 3
    assert classed(_block(), "app-fin__code") == []


# -------------------------------------------------------------------------------- the figures


def _figure(unit: str, value: Any, scale: str = "m", digits: int = 0, key: str = "x") -> Any:
    return _tab("figure", _row(key, "A line", "line", unit, []), value, scale, digits)


def test_a_figure_s_text() -> None:
    """An amount and a share count in millions grouped, with one decimal where the table's
    largest amount is under a thousand million, or in billions to two decimals; a dash for none
    and for 0. Per share and a plain ratio to two decimals, a percent to one (the dividend yield
    to two), a multiple to one with x and a dash at 0, days to none. Below zero a minus, none
    where the figure rounds to zero."""
    assert _figure("money", 471_368e6) == "471,368"
    assert _figure("money", 471_368e6, "b") == "471.37"
    assert _figure("money", -84_170e6) == "−84,170"
    assert _figure("money", -84_170e6, "b") == "−84.17"
    assert _figure("money", 12.34e6, "m", 1) == "12.3"
    assert _figure("money", 0) == DASH
    assert _figure("money", None) == DASH
    assert _figure("money", -3, "b") == "0.00"
    assert _figure("shares", 15.2e9) == "15,200"
    assert _figure("shares", 15.2e9, "b") == "15.20"
    assert _figure("shares", 0, "b") == DASH
    assert _figure("perShare", 7.906) == "7.91"
    assert _figure("perShare", -0.414) == "−0.41"
    assert _figure("perShare", None) == DASH
    assert _figure("percent", 0.33) == "33.0%"
    assert _figure("percent", -0.0714) == "−7.1%"
    assert _figure("percent", 0.0042, key="dividendYield") == "0.42%"
    assert _figure("percent", 0.0042) == "0.4%"
    assert _figure("multiple", 37.94) == "37.9x"
    assert _figure("multiple", 0) == DASH
    assert _figure("ratio", 1.034) == "1.03"
    assert _figure("ratio", None) == DASH
    assert _figure("days", 61.4) == "61"

    def table(*values: Any, unit: str = "money") -> dict[str, Any]:
        return {"columns": _years(), "rows": [_row("x", "A line", "line", unit, list(values))]}

    assert _tab("digits", table(640e6, -120e6)) == 1
    assert _tab("digits", table(-999.9e6, None)) == 1
    assert _tab("digits", table(5e9, 12e6)) == 0
    assert _tab("digits", table(-1e9, 0)) == 0
    assert _tab("digits", table(4.2e9, unit="shares")) == 0  # no amount: no decimal
    assert _tab("digits", RATIOS) == 0
    assert _tab("digits", EMPTY) == 0

    small = copy.deepcopy(ANSWER)
    small["segments"]["region"] = {
        "columns": _years(),
        "rows": [_row("Americas", "Americas", "line", "money", [640e6, 12.34e6])],
    }
    product, region = classed(_block(small, kind="segments"), "app-fin__table")
    assert _grid(product)[1][1:] == ["40,100", "47,900"]  # each table judged by itself
    assert _grid(region)[1][1:] == ["640.0", "12.3"]
    ratios = _grid(classed(_block(kind="ratios"), "app-fin__table")[0])
    assert ratios[1:] == [
        ["MARGINS"],
        ["Gross", "45.8%", "47.6%"],
        ["VALUATION"],
        ["P/E", "24.8x", DASH],
        ["DIVIDENDS"],
        ["Yield", "0.51%", "0.42%"],
    ]
    billions = _grid(classed(_block(scale="b"), "app-fin__table")[0])
    assert billions[0][0] == "USD, billions, except per share"
    assert billions[1] == ["Revenue", "61.20", "72.48"]
    assert billions[5] == ["EPS", "2.10", "2.72"]
    assert billions[6] == ["Shares, basic", "5.21", "5.10"]


# ------------------------------------------------------------------------------- the unit kept


def test_the_unit_is_millions_where_storage_fails() -> None:
    """The unit is read from the browser's store and written to it, each inside a try: no store,
    one that throws or one holding anything but b gives Millions, and a write never throws."""
    assert _tab("storedScale") == "m"  # the harness has no localStorage
    for store, unit in (
        (None, "m"),
        ("throws", "m"),
        ({}, "m"),
        ({KEY: "b"}, "b"),
        ({KEY: "m"}, "m"),
        ({KEY: "x"}, "m"),
        ({"fin-scale": "b"}, "m"),
    ):
        [stored] = _drive(store, [{"do": "stored"}])
        assert (stored["result"], stored["threw"]) == (unit, False), store
    for store in (None, "throws"):
        trace = _drive(
            store,
            [
                {"do": "keep", "scale": "b"},
                {"do": "mount", "answer": ANSWER},
                _press("app-fin__scale", "Billions"),
                {"do": "mount", "answer": ANSWER},
            ],
        )
        assert [step["threw"] for step in trace] == [False] * 4, store
        assert [_view(step["view"]) for step in trace] == [
            None,
            ("Income statement", "Millions", "Annual"),
            ("Income statement", "Billions", "Annual"),
            ("Income statement", "Millions", "Annual"),
        ], store
    [kept] = _drive({}, [{"do": "keep", "scale": "b"}])
    assert kept["store"] == {KEY: "b"}
    [opened] = _drive({KEY: "b"}, [{"do": "mount", "answer": ANSWER}])
    assert _view(opened["view"]) == ("Income statement", "Billions", "Annual")


# ------------------------------------------------------------------------ the lines on the chart


def _line(kind: str, key: str, table: str | None = None) -> dict[str, Any]:
    """A line as a row knows it: its sub-tab, its table and its key."""
    return {"kind": kind, "table": table, "key": key}


def _pick(kind: str, key: str, table: str | None = None, slot: int = 0) -> dict[str, Any]:
    """A line on the chart, with its colour slot."""
    return _line(kind, key, table) | {"slot": slot}


REVENUE = _pick("income", "revenue")
GROSS = _line("income", "grossProfit")
EPS = _line("income", "eps")
COST = _line("income", "costOfRevenue")
SHARES = _line("income", "weightedAverageShsOut")
MARGIN = _line("ratios", "grossProfitMargin")


def _classes(e: dict[str, Any]) -> set[str]:
    return set(str(e["props"].get("className") or "").split())


def _adds(tree: Any) -> dict[str, dict[str, Any]]:
    """Each line's row's button by the row's name: its words, aria-pressed, aria-label, title,
    type, whether it is disabled, and the classes of the swatch it holds (None for none)."""
    found = {}
    for row in _typed(tree, "tr"):
        buttons = classed(row, "app-fin__add")
        if not buttons:
            continue
        [button] = buttons
        name = _typed(row, "th")[0]
        swatches = [e for e in elements(button) if e is not button]
        found[_words(name)] = {
            "text": text(button),
            "pressed": button["props"]["aria-pressed"],
            "label": button["props"]["aria-label"],
            "title": button["props"]["title"],
            "disabled": bool(button["props"].get("disabled")),
            "type": button["props"]["type"],
            "swatch": _classes(swatches[0]) if swatches else None,
        }
    return found


def test_the_plus_adds_a_line_and_takes_it_off() -> None:
    """A press on a row's + adds its line at the lowest free slot, after the lines on the chart;
    a press on its swatch takes it off, and the one line left takes slot 0. The press is the
    button's alone: its click goes no further, so the row's own press, which charts its line
    alone, does not follow, and the row takes no Enter or Space that comes from its button."""
    two = _tab("toggle", [REVENUE], GROSS)
    assert two == [REVENUE, GROSS | {"slot": 1}]
    assert _tab("toggle", two, _line("income", "revenue")) == [GROSS | {"slot": 0}]
    assert _tab("toggle", [], GROSS) == [GROSS | {"slot": 0}]

    trace = _drive(
        None,
        [
            {"do": "mount", "answer": ANSWER},
            {"do": "add", "text": "Gross profit"},
            {"do": "add", "text": "EPS"},
            {"do": "add", "text": "Revenue"},
            {"do": "row", "text": "Cost of revenue", "key": "Enter", "button": True},
            {"do": "row", "text": "Cost of revenue", "key": " ", "button": True},
            {"do": "add", "text": "Revenue"},
        ],
        CHARTED,
    )
    assert [step["threw"] for step in trace] == [False] * 7
    assert [step["picks"] for step in trace] == [
        [REVENUE],
        [REVENUE, GROSS | {"slot": 1}],
        [REVENUE, GROSS | {"slot": 1}, EPS | {"slot": 2}],
        [GROSS | {"slot": 1}, EPS | {"slot": 2}],
        [GROSS | {"slot": 1}, EPS | {"slot": 2}],
        [GROSS | {"slot": 1}, EPS | {"slot": 2}],
        [GROSS | {"slot": 1}, EPS | {"slot": 2}, REVENUE],
    ]
    assert [step["on"] for step in trace] == [
        ["Revenue"],
        ["Revenue", "Gross profit"],
        ["Revenue", "Gross profit", "EPS"],
        ["Gross profit", "EPS"],
        ["Gross profit", "EPS"],
        ["Gross profit", "EPS"],
        ["Revenue", "Gross profit", "EPS"],
    ]
    assert [step["stopped"] for step in trace] == [False, True, True, True, False, False, True]
    assert [step["prevented"] for step in trace[4:6]] == [False, False]
    script = _static_file("company_financials.js")
    assert "event.target !== event.currentTarget" in script


def test_the_last_line_stays_and_a_fifth_is_refused() -> None:
    """The last line on the chart cannot be taken off, and the chart holds four lines: a fifth
    is refused. At four, the button of every row off the chart is disabled, with the title that
    says why; a row on the chart keeps its own."""
    assert _tab("toggle", [REVENUE], _line("income", "revenue")) == [REVENUE]
    assert _tab("drop", [REVENUE], REVENUE) == [REVENUE]
    four = [REVENUE, GROSS | {"slot": 1}, EPS | {"slot": 2}, COST | {"slot": 3}]
    assert _tab("toggle", four, SHARES) == four
    assert _tab("toggle", four, MARGIN) == four
    script = _static_file("company_financials.js")
    assert re.search(r"\n  var MAX = 4;", script)
    assert "MAX: MAX" in script

    adds = _adds(_tab("block", ANSWER, VIEW, four, None))
    for name in ("Revenue", "Cost of revenue", "Gross profit", "EPS"):
        assert adds[name]["pressed"] == "true", name
        assert (adds[name]["label"], adds[name]["title"]) == (TAKE, TAKE), name
        assert adds[name]["disabled"] is False, name
    for name in ("General and administrative", "Shares, basic"):
        assert adds[name] == {
            "text": "+",
            "pressed": "false",
            "label": ADD,
            "title": FULL,
            "disabled": True,
            "type": "button",
            "swatch": None,
        }, name
    three = _adds(_tab("block", ANSWER, VIEW, four[:3], None))
    assert (three["Shares, basic"]["disabled"], three["Shares, basic"]["title"]) == (False, ADD)
    ratios = _adds(_tab("block", ANSWER, VIEW | {"kind": "ratios"}, four, None))
    assert {a["disabled"] for a in ratios.values()} == {True}

    trace = _drive(
        None,
        [
            {"do": "mount", "answer": ANSWER},
            {"do": "add", "text": "Gross profit"},
            {"do": "add", "text": "EPS"},
            {"do": "add", "text": "Cost of revenue"},
            {"do": "add", "text": "Shares, basic"},
            {"do": "drop", "pick": REVENUE},
            {"do": "drop", "pick": GROSS | {"slot": 1}},
            {"do": "drop", "pick": EPS | {"slot": 2}},
            {"do": "drop", "pick": COST | {"slot": 3}},
        ],
        CHARTED,
    )
    assert [len(step["picks"]) for step in trace] == [1, 2, 3, 4, 4, 3, 2, 1, 1]
    assert trace[4]["picks"] == four
    assert trace[-1]["picks"] == [COST | {"slot": 0}]


def test_a_line_keeps_its_colour_while_another_leaves() -> None:
    """A line keeps its slot until it leaves the chart: taking one off repaints none of the
    others, and the next line added takes the lowest slot free. The one line left takes slot 0.
    The labels' x takes a line off, down to one line, which stays."""
    three = [REVENUE, GROSS | {"slot": 1}, EPS | {"slot": 2}]
    left = _tab("drop", three, GROSS | {"slot": 1})
    assert left == [REVENUE, EPS | {"slot": 2}]
    assert _tab("toggle", left, COST) == [REVENUE, EPS | {"slot": 2}, COST | {"slot": 1}]
    assert _tab("toggle", three, GROSS) == left
    assert _tab("drop", left, REVENUE) == [EPS | {"slot": 0}]
    assert _tab("drop", three, SHARES | {"slot": 3}) == three  # a line not on the chart

    trace = _drive(
        None,
        [
            {"do": "mount", "answer": ANSWER},
            {"do": "add", "text": "Gross profit"},
            {"do": "add", "text": "EPS"},
            {"do": "add", "text": "Cost of revenue"},
            {"do": "drop", "pick": GROSS | {"slot": 1}},
            {"do": "add", "text": "Shares, basic"},
            {"do": "drop", "pick": REVENUE},
            {"do": "drop", "pick": EPS | {"slot": 2}},
            {"do": "drop", "pick": SHARES | {"slot": 1}},
            {"do": "drop", "pick": COST | {"slot": 0}},
        ],
        CHARTED,
    )
    assert [step["threw"] for step in trace] == [False] * 10
    assert [[p["slot"] for p in step["picks"]] for step in trace] == [
        [0],
        [0, 1],
        [0, 1, 2],
        [0, 1, 2, 3],
        [0, 2, 3],
        [0, 2, 3, 1],
        [2, 3, 1],
        [3, 1],
        [0],
        [0],
    ]
    assert trace[4]["picks"] == [REVENUE, EPS | {"slot": 2}, COST | {"slot": 3}]
    assert trace[-1]["picks"] == [COST | {"slot": 0}]


def test_the_picks_stay_across_sub_tabs_and_go_with_the_company() -> None:
    """The lines on the chart stay as the reader changes sub-tab and period, so a statement's
    line and a ratio stand together; another company's answer, a new tab keyed on its symbol,
    opens on its Revenue alone."""
    trace = _drive(
        None,
        [
            {"do": "mount", "answer": ANSWER},
            {"do": "add", "text": "Gross profit"},
            _press("app-fin__tab", "Ratios"),
            {"do": "add", "text": "Gross"},
            _press("app-fin__tab", "Income statement"),
            _press("app-fin__period", "Quarterly"),
            _press("app-fin__tab", "Segments"),
            {"do": "land", "answer": ANSWER | {"symbol": "BETA"}},
        ],
        CHARTED,
    )
    held = [REVENUE, GROSS | {"slot": 1}, MARGIN | {"slot": 2}]
    assert [step["picks"] for step in trace] == [
        [REVENUE],
        held[:2],
        held[:2],
        held,
        held,
        held,
        held,
        [REVENUE],
    ]
    assert [step["on"] for step in trace] == [
        ["Revenue"],
        ["Revenue", "Gross profit"],
        [],
        ["Gross"],
        ["Revenue", "Gross profit"],
        ["Revenue"],
        [],
        [],  # BETA's tab opens on the sub-tab kept, Segments, its Revenue on the chart
    ]
    drawn = node("companyPage.draw.financials", [ANSWER | {"symbol": "BETA"}], *SCRIPTS)
    assert drawn["props"]["key"] == "BETA"


def test_the_picks_stay_when_the_tab_opens_again_on_the_same_company() -> None:
    """The lines on the chart stay when the reader leaves the tab for another tab of the same
    company and comes back, each in its slot, and when the same company's answer lands again; they
    go when another company's tab opens, or its answer lands, which opens on its Revenue alone, and
    the first company's tab opens on its Revenue alone after that."""
    beta = ANSWER | {"symbol": "BETA"}
    held = [GROSS | {"slot": 1}, EPS | {"slot": 2}]
    trace = _drive(
        None,
        [
            {"do": "mount", "answer": ANSWER},
            {"do": "add", "text": "Gross profit"},
            {"do": "add", "text": "EPS"},
            {"do": "add", "text": "Revenue"},
            {"do": "mount", "answer": ANSWER},
            {"do": "land", "answer": ANSWER},
            {"do": "mount", "answer": beta},
            {"do": "mount", "answer": ANSWER},
            {"do": "add", "text": "EPS"},
            {"do": "land", "answer": beta},
            {"do": "mount", "answer": ANSWER},
        ],
        CHARTED,
    )
    assert [step["threw"] for step in trace] == [False] * 11
    assert [step["picks"] for step in trace] == [
        [REVENUE],
        [REVENUE, GROSS | {"slot": 1}],
        [REVENUE, *held],
        held,
        held,  # the tab opens again on the same company: its lines, each in its slot
        held,  # the same company's answer lands again
        [REVENUE],  # another company's tab
        [REVENUE],  # the first company's again, after another's
        [REVENUE, EPS | {"slot": 1}],
        [REVENUE],  # another company's answer lands
        [REVENUE],
    ]
    assert trace[4]["on"] == ["Gross profit", "EPS"]


def test_a_kept_pick_whose_line_is_gone_breaks_nothing() -> None:
    """A line kept on the chart that the company's next answer no longer holds: the tab opens
    again on the lines it held, draws, and the chart draws the lines the answer holds."""
    gone = copy.deepcopy(ANSWER)
    gone["statements"]["income"]["annual"]["rows"] = [
        row for row in INCOME["rows"] if row["key"] != "grossProfit"
    ]
    trace = _drive(
        None,
        [
            {"do": "mount", "answer": ANSWER},
            {"do": "add", "text": "Gross profit"},
            {"do": "mount", "answer": gone},
        ],
        CHARTED,
    )
    assert [step["threw"] for step in trace] == [False] * 3
    assert trace[-1]["picks"] == [REVENUE, GROSS | {"slot": 1}]
    assert trace[-1]["on"] == ["Revenue"]
    chart = node(
        "companyFinancialsChart.block",
        [gone, trace[-1]["picks"], "annual", "m", None, 900, None],
        *CHARTED,
    )
    [head] = classed(chart, "app-fin__chead")
    assert text(head["props"]["children"][0]) == "Revenue"


def test_a_row_on_the_chart_shows_its_colour() -> None:
    """A row on the chart carries its slot's class, which gives it its line's colour: its button
    pressed, holding the line's swatch, a square for bars and a round dot for a line, with no
    words; a row off the chart reads +. A section head has no button. The CSS gives each of the
    four slots its series colour, chart-1 to chart-4, which the row's 2px bar and the swatch
    wear, and no colour of its own; no text wears one."""
    picks = [REVENUE, EPS | {"slot": 2}, MARGIN | {"slot": 3}]
    tree = _tab("block", ANSWER, VIEW, picks, None)
    rows = {_words(_typed(r, "th")[0]): r for r in _typed(tree, "tr")[1:]}
    assert _classes(rows["Revenue"]) == {"is-total", "is-on", "is-s0"}
    assert _classes(rows["EPS"]) == {"is-on", "is-s2"}
    adds = _adds(tree)
    for name in ("Revenue", "EPS"):
        assert adds[name]["text"] == ""
        assert adds[name]["pressed"] == "true"
        assert adds[name]["swatch"] == {"app-fin__swatch"}
    assert adds["Gross profit"]["text"] == "+"
    assert adds["Gross profit"]["pressed"] == "false"
    assert (adds["Gross profit"]["label"], adds["Gross profit"]["title"]) == (ADD, ADD)
    assert adds["Gross profit"]["swatch"] is None
    ratios = _tab("block", ANSWER, VIEW | {"kind": "ratios"}, picks, None)
    assert _adds(ratios)["Gross"]["swatch"] == {"app-fin__swatch", "app-fin__swatch--round"}
    assert [_classes(r) for r in _typed(ratios, "tr") if "is-on" in _classes(r)] == [
        {"is-on", "is-s3"}
    ]
    for head in classed(ratios, "is-head"):
        assert classed(head, "app-fin__add") == []
    [name] = _typed(rows["Revenue"], "th")
    assert _button(name["props"]["children"][0])  # the button before the name

    css = _rules(_static_file("index.html"))
    for slot in range(4):
        assert css[f".app-fin .is-s{slot}"] == f"--fin-series: var(--chart-{slot + 1});"
    assert "background: var(--fin-series);" in css[".app-fin__swatch, .app-fin__key"]
    assert "border-radius: 50%;" in css[".app-fin__swatch--round, .app-fin__key--round"]
    assert "opacity: 0.35;" in css[".app-fin__add:disabled"]
    painted = " ".join(css.values())
    assert not re.search(r"(?<![-\w])color: var\(--(fin-series|chart-)", painted)  # no text
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", painted) == []


# -------------------------------------------------------------------------------- the layout


def _rules(css: str, indent: int = 2) -> dict[str, str]:
    """Each tab's rule of ``css`` at ``indent``, the page's or a media rule's, by its selector,
    its declarations on one line."""
    found = re.findall("\n" + " " * indent + r"(\.app-fin(?![a-z])[^{]*)\{([^}]*)\}", css)
    return {selector.strip(): " ".join(body.split()) for selector, body in found}


def test_the_table_scrolls_sideways_inside_the_block_its_first_column_in_place() -> None:
    """The table scrolls sideways inside its block, never the page; the first column stays in
    place, on the block's own ground so the figures pass under it; under 700px it narrows to
    168px and a long name wraps. The controls' row wraps. Nothing moves."""
    html = _static_file("index.html")
    css = _rules(html)
    assert "overflow-x: auto;" in css[".app-fin__scroll"]
    first = css[".app-fin__table th:first-child, .app-fin__table td:first-child"]
    assert "position: sticky;" in first
    assert "left: 0;" in first
    assert "background: var(--surface-raised);" in first
    assert "flex-wrap: wrap;" in css[".app-fin__bar"]
    narrow = re.search(r"@media \(width < 700px\) \{(.*?)\n  \}", html, re.DOTALL)
    assert narrow is not None
    rules = _rules(narrow.group(1), 4)
    first = rules[".app-fin__table th:first-child, .app-fin__table td:first-child"]
    assert "min-width: 168px;" in first
    assert "white-space: normal;" in first
    assert all("transition" not in body and "animation" not in body for body in css.values())
    colours = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", " ".join(css.values()))
    assert colours == []  # the tokens' colours alone
