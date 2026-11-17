"""The ticker in the screen's table (spec 2026-11-16 company page, 12): in the Ticker cell of the
screen's table and of a watchlist's, the ticker's text is a link to the company page,
``#company/<symbol>``, the symbol encoded. A click on it, or Enter on it, stops at the link, so the
row does not open the drawer and the browser follows the address; the watchlist mark keeps its own
click. The link is ScreenTable's ``companyHref``, a ``fairband:`` patch of the vendored bundle, and
without it the cell is drawn as it was. It reads as the ticker does, takes an underline on hover
and the focus ring on focus.

And the report page (13): its head gains Company page, a link to the company page, and it loses its
Tables button, its state and the ``tableView`` it handed each chart; the vendored components keep
the prop, unset.

The bundle and the page's scripts run in node (``support.page``), and the tests read the trees
ScreenTable and the report page's head draw; a prop written ``{"$page": <helper>}`` is the page's
own function (``tests/web/page.mjs``). The handlers and the shell are read as text."""

import copy
import re
from pathlib import Path
from typing import Any

import pytest
from support import page_answers as answers
from support.page import NODE, STATIC, classed, elements, node
from support.web import _component_file, _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

REPORT = STATIC / "report.js"
LINK = "fb-screen__company"
# A screen row on a list and with a published report, so its Ticker cell holds both marks.
ROW: dict[str, Any] = {
    "ticker": "BRK.B",
    "name": "Brookhaven Kettle Holdings",
    "phase": 5,
    "fairLow": 410.0,
    "fairHigh": 520.0,
    "fairValue": 465.0,
    "buyLevel": 390.0,
    "trimLevel": 560.0,
    "price": 471.2,
    "mechanical": 465.0,
    "reviewed": None,
    "watched": True,
    "watchlists": [1],
    "covered": {"at": "2026-11-10T09:00:00+00:00", "actor": "claude-opus-5-5", "expired": False},
}
# The watchlist mark and the coverage mark of ROW's cell, as the bundle draws them, the handlers
# left out by the JSON the harness answers in.
MARK: dict[str, Any] = {
    "type": "button",
    "props": {
        "type": "button",
        "className": "fb-watch control fb-watch--on",
        "aria-label": "Watchlists for BRK.B",
        "aria-pressed": "true",
        "children": ["▶"],
    },
}
COVERED: dict[str, Any] = {
    "type": "span",
    "props": {
        "className": "fb-covered",
        "title": "Report 10 Nov 2026 by claude-opus-5-5",
        "role": "img",
        "aria-label": "Report 10 Nov 2026 by claude-opus-5-5",
        "children": ["◆"],
    },
}


def _table(rows: list[dict[str, Any]], linked: bool) -> Any:
    """ScreenTable on ``rows`` as the screen hands it its props, its marks' and its rows' handlers
    the page's own, with the page's ``companyHref`` where ``linked``."""
    props: dict[str, Any] = {
        "rows": rows,
        "chooser": False,
        "onOpen": {"$page": "openRow"},
        "onWatch": {"$page": "watch"},
    }
    if linked:
        props["companyHref"] = {"$page": "companyHref"}
    return node("Fairband.ScreenTable", [props])


def _cell(tree: Any) -> dict[str, Any]:
    [cell] = classed(tree, "fb-screen__ticker")
    return cell


def _unlinked(tree: Any) -> Any:
    """``tree`` with each ticker's link replaced by its text; a Fragment's element has no
    ``type``."""
    if isinstance(tree, list):
        return [_unlinked(kid) for kid in tree]
    if not isinstance(tree, dict):
        return tree
    if tree.get("type") == "a" and tree["props"].get("className") == LINK:
        [words] = tree["props"]["children"]
        return words
    props = dict(tree["props"])
    props["children"] = _unlinked(props.get("children"))
    return {**tree, "props": props}


def _ticker_column(bundle: str) -> str:
    """The bundle's Ticker column, its cell and its patches."""
    return bundle[
        bundle.index("{ key: 'ticker', head: 'Ticker'") : bundle.index("{ key: 'name', head:")
    ]


def _function(script: str, name: str) -> str:
    """The text of the script's ``function <name>(``, to its closing brace."""
    start = script.index(f"  function {name}(")
    return script[start : script.index("\n  }\n", start)]


def _rule(selector: str) -> str:
    """The declarations of the page's one rule whose line opens with ``selector``, on one line."""
    css = _static_file("index.html")
    ends = [m.end() for m in re.finditer(r"(?m)^[ \t]*" + re.escape(selector), css)]
    assert len(ends) == 1, selector
    return " ".join(css[ends[0] : css.index("}", ends[0])].split())


# ------------------------------------------------------------------------------- the ticker's link


def test_the_ticker_is_a_link_given_the_prop() -> None:
    """Given companyHref, the ticker's text is a link to the address it gives for the row: the
    page's own, the company page, the symbol encoded as a link encodes it, so BRK.B keeps its dot
    and a character a hash cannot hold is escaped. The marks before and after it stay."""
    cell = _cell(_table([ROW], linked=True))
    assert cell["props"]["className"] == "fb-screen__ticker ticker"
    mark, link, covered = cell["props"]["children"]
    assert link == {
        "type": "a",
        "props": {"className": LINK, "href": "#company/BRK.B", "children": ["BRK.B"]},
    }
    assert (mark, covered) == (MARK, COVERED)
    assert node("companyHref", [ROW]) == "#company/BRK.B"
    assert node("companyHref", [ROW | {"ticker": "KT/A B"}]) == "#company/KT%2FA%20B"


def test_the_cell_without_the_prop_is_as_before() -> None:
    """Without companyHref no link is drawn: the ticker is the cell's text between its marks, and
    the whole table is the table drawn with the prop but for each link, its text in its place; a
    row on no list and with no report has the ticker alone."""
    plain = _table([ROW], linked=False)
    assert [e for e in elements(plain) if e.get("type") == "a"] == []
    assert _cell(plain) == {
        "type": "td",
        "props": {"className": "fb-screen__ticker ticker", "children": [MARK, "BRK.B", COVERED]},
    }
    linked = _table([ROW, ROW | {"ticker": "ACME", "watched": False, "covered": None}], True)
    assert len(classed(linked, LINK)) == 2
    assert _unlinked(linked) == _table(
        [ROW, ROW | {"ticker": "ACME", "watched": False, "covered": None}], linked=False
    )
    bare = node("Fairband.ScreenTable", [{"rows": [ROW | {"watched": False, "covered": None}]}])
    assert _cell(bare)["props"]["children"] == [None, "BRK.B", None]


def test_the_link_stops_its_click_and_its_enter() -> None:
    """A click on the link stops there, so the row's onOpen does not run, and does not prevent
    the browser, which follows the address in the tab, the app's own hash: no target. Enter on the
    focused link stops there too, so the row neither opens nor prevents the link's own Enter. The
    patch is marked as the watchlist mark's is, and index.d.ts documents the prop."""
    ticker = _ticker_column(_component_file("bundle.js"))
    patch = ticker[ticker.index("// fairband: given companyHref") :]
    assert "(spec 2026-11-16 company page, 12)" in patch[: patch.index("p.companyHref ?")]
    link = patch[patch.index("p.companyHref ?") : patch.index(": r.ticker,") + len(": r.ticker,")]
    assert link == (
        "p.companyHref ? h('a', {\n"
        "            className: 'fb-screen__company', href: p.companyHref(r),\n"
        "            onClick: function (e) { e.stopPropagation(); },\n"
        "            onKeyDown: function (e) { if (e.key === 'Enter') e.stopPropagation(); }\n"
        "          }, r.ticker) : r.ticker,"
    )
    # the link stands between the watchlist mark and the coverage mark
    assert ticker.index("p.onWatch ? h('button', {") < ticker.index(link)
    assert ticker.index(link) < ticker.index("r.covered ? h('span', {")
    declarations = _component_file("index.d.ts")
    props = re.search(r"export interface ScreenTableProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    block = props.group(1)
    declared = block.index("  companyHref?: (row: ScreenRow) => string;")
    doc = block[block.rindex("/**", 0, declared) : declared]
    assert "fairband:" in doc and "(spec 2026-11-16 company page, 12)" in doc
    assert block.index("onWatch?: (row: ScreenRow) => void;") < declared


def test_the_screen_and_the_watchlists_pass_the_prop() -> None:
    """The screen's table and each watchlist's hand ScreenTable the one address the page keeps,
    FairbandPage.companyHref: the company page of the row's ticker, encoded."""
    app = _static_file("app.js")
    assert "return '#company/' + encodeURIComponent(row.ticker);" in _function(app, "companyHref")
    shared = app[app.index("window.FairbandPage = {") :]
    assert "companyHref: companyHref," in shared[: shared.index("};")]
    assert "companyHref: companyHref," in _function(app, "render")
    assert "companyHref: P.companyHref," in _function(_static_file("watchlists.js"), "section")


def test_the_link_reads_as_the_ticker() -> None:
    """The cell's type and colour, no underline at rest, an underline on hover and the app's focus
    ring on focus. Its class is its own: no rule of the bundle's, no other element and no other
    script carries it."""
    rule = _rule(".fb-screen__company {")
    assert "color: inherit;" in rule and "text-decoration: none;" in rule
    assert _rule(".fb-screen__company:hover {") == "text-decoration: underline;"
    assert _rule(".fb-screen__company:focus-visible {") == (
        "outline: 2px solid var(--focus-ring); outline-offset: 2px;"
    )
    assert LINK not in _component_file("bundle.css")
    token = re.compile(r"(?<![\w-])" + re.escape(LINK) + r"(?![\w-])")
    assert len(token.findall(_component_file("bundle.js"))) == 1
    scripts: list[Path] = sorted(STATIC.glob("*.js"))
    for script in scripts:
        assert not token.findall(script.read_text(encoding="utf-8")), script.name


# ------------------------------------------------------------------------------- the report page


def test_the_report_page_links_to_the_company_page() -> None:
    """The head's right end: the one headline figure and the price, then Company page, a link in
    the button's look to the company page, the symbol encoded as the screen's link encodes it.
    The page draws no link back to the screen: the header's Screen view is the way back."""
    detail = copy.deepcopy(answers.DETAIL)
    detail["result"]["symbol"] = "BRK.B"
    head = node("reportHead", [detail], REPORT)
    assert head["props"]["className"] == "app-report__head"
    ident, side = head["props"]["children"]
    assert ident["props"]["className"] == "app-report__id"
    assert side["props"]["className"] == "app-report__side"
    figures, link = side["props"]["children"]
    assert figures["props"]["className"] == "app-report__figures"
    assert link["props"] == {"href": "#company/BRK.B", "children": ["Company page"]}
    assert "h(F.Button, { href: '#company/' + encodeURIComponent(r.symbol) }, 'Company page')" in (
        " ".join(_function(_static_file("report.js"), "head").split())
    )
    assert "function back(" not in _static_file("report.js")
    assert "align-items: baseline;" in _rule(".app-report__side {")


def test_the_report_page_has_no_tables_button() -> None:
    """No Tables button above the reader, no state for it and no toggle; the page hands the charts
    the report and the series alone, and no chart is handed tableView. The bundle's charts keep
    the prop, unset."""
    report = _static_file("report.js")
    charts = _static_file("charts.js")
    for name, script in (("report.js", report), ("charts.js", charts)):
        for gone in ("Tables", "toggleTables", "tableView", "table toggle"):
            assert gone not in script, (name, gone)
    assert "state.tables" not in report
    assert "charts: P.reportCharts.draw(report, state.series)" in _function(report, "reader")
    assert "function draw(report, series) {" in charts
    assert "h(F.Button, { size: 'sm', onClick: download }, 'Download .md')" in (
        _function(report, "meta")
    )
    assert _component_file("bundle.js").count("show: p.tableView,") == 4
    assert _component_file("index.d.ts").count("tableView?: boolean;") == 4
