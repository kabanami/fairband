"""The company page's view (the company page's design, 7): its address, the head it draws on
every tab, the tabs' row with the data date, and the helpers and formatters the tabs' blocks are
built from (14.1). The page's own script, company.js, runs in node after the bundle and app.js
(``support.page``), and the tests read the trees its builders return; controls.js, which the
harness does not load, and the reads around the builders are read as text.

The company is ``page_answers``' LFOX: valued at $196.50 against a price of $182.40, a wide moat,
listed on NYSE, its quote's change +$2.15 (+1.1928%)."""

import json
import re
import subprocess
from typing import Any

import pytest
from support import page_answers as answers
from support.page import NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

COMPANY = STATIC / "company.js"
QUOTE = answers.OVERVIEW["quote"]


def _page(helper: str, *args: Any) -> Any:
    """What ``companyPage.<helper>`` returns on ``args``, company.js loaded after app.js."""
    return node("companyPage." + helper, list(args), COMPANY)


def _head(detail: dict[str, Any], quote: dict[str, Any] | None = QUOTE) -> Any:
    return _page("head", detail, quote)


def _function(script: str, name: str) -> str:
    """The text of the script's ``function <name>(``, to its closing brace."""
    start = script.index(f"  function {name}(")
    return script[start : script.index("\n  }\n", start)]


def _in_order(within: str, *parts: str) -> None:
    """Each part is in ``within``, each after the one before it."""
    at = [within.index(part) for part in parts]
    assert at == sorted(at), parts


def _drawn_in_order(tree: Any, *parts: dict[str, Any]) -> None:
    """Each of ``parts``, elements of ``tree``, comes after the one before it."""
    at = [[id(e) for e in elements(tree)].index(id(part)) for part in parts]
    assert at == sorted(at)


def _texts_in_order(tree: Any, *words: str) -> None:
    """Each of ``words`` is the text of an element of ``tree``, each after the one before it."""
    found = [text(e) for e in elements(tree)]
    at = [found.index(word) for word in words]
    assert at == sorted(at), words


def _classes(tree: Any) -> list[str]:
    """The class names of every element of ``tree``, in order."""
    return [str(e["props"].get("className") or "") for e in elements(tree)]


def _badges(tree: Any) -> list[dict[str, Any]]:
    """The bundle's PhaseBadge elements of a helper's tree, which the harness leaves undrawn,
    their props as given (``page.mjs`` draws a bundle component only for a ``Fairband.``
    helper)."""
    return [e for e in elements(tree) if "phase" in e["props"]]


def _button(tree: Any, words: str) -> dict[str, Any]:
    """The one bundle Button of ``tree`` whose text is ``words``, undrawn as ``_badges``'."""
    [button] = [e for e in elements(tree) if e["props"].get("children") == [words]]
    return button


def _rule(selector: str) -> str:
    """The declarations of the page's one rule whose line opens with ``selector``, on one line."""
    css = _static_file("index.html")
    ends = [m.end() for m in re.finditer(r"(?m)^[ \t]*" + re.escape(selector), css)]
    assert len(ends) == 1, selector
    return " ".join(css[ends[0] : css.index("}", ends[0])].split())


# ------------------------------------------------------------------------------------ the head


def test_the_head_s_parts() -> None:
    """Left: the logo on the drawer's tile at 40px, the name, the ticker, the phase badge, the
    moat stamp, and one caption, the exchange, the sector and the industry. Right: the latest
    snapshot's price in figure-lg and the day of its close."""
    tree = _head(answers.DETAIL)
    [logo] = classed(tree, "app-company__logo")
    assert logo["type"] == "img"
    assert logo["props"]["src"] == answers.DETAIL["logo"]
    assert "app-logo" in logo["props"]["className"].split()
    [name] = classed(tree, "app-company__name")
    assert text(name) == "Lanternfield Optics Ltd"
    [ticker] = classed(tree, "ticker")
    assert text(ticker) == "LFOX"
    [badge] = _badges(tree)
    assert (badge["props"]["phase"], badge["props"]["size"]) == (4, "sm")
    [stamp] = classed(tree, "app-moat")
    _drawn_in_order(tree, logo, name, ticker, badge, stamp)
    [line] = classed(tree, "app-company__sub")
    assert text(line) == "NYSE · Technology · Semiconductors"
    [price] = classed(tree, "figure-lg")
    assert text(price) == "$182.40"
    [close] = classed(tree, "app-company__at")
    assert text(close) == "close 16 Nov 2026"


def test_the_head_of_a_company_with_less_on_file() -> None:
    """No universe row: no name and no caption line. No logo, no phase, no price date: none of
    them is drawn; a missing price is a dash."""
    bare = answers.detail(company=None, logo=None)
    bare["result"] |= {"price": None, "price_date": None}
    bare["result"]["phase"] |= {"phase": None}
    tree = _head(bare)
    assert classed(tree, "app-company__name") == []
    assert classed(tree, "app-company__sub") == []
    assert classed(tree, "app-company__logo") == []
    assert _badges(tree) == []
    assert classed(tree, "app-company__at") == []
    [price] = classed(tree, "figure-lg")
    assert text(price) == "—"
    [ticker] = classed(tree, "ticker")
    assert text(ticker) == "LFOX"


def test_the_moat_stamp_s_three_words_and_none() -> None:
    """An outlined label, in the words of the Words table; none without a moat."""
    for moat, words in (("Wide", "WIDE MOAT"), ("Narrow", "NARROW MOAT"), ("None", "NO MOAT")):
        stamp = node("moatStamp", [{"moat": moat}])
        assert stamp["type"] == "span"
        assert stamp["props"]["className"] == "label app-moat"
        assert text(stamp) == words
    assert node("moatStamp", [{"moat": None}]) is None
    assert node("moatStamp", [{}]) is None


def test_the_head_stamps_the_moat_in_force_and_none_on_a_refused_row() -> None:
    """The detail's moat is the review's where a review counts (the server's rule); a refused row
    has none, and no stamp."""
    [stamp] = classed(_head(answers.reviewed_detail()), "app-moat")
    assert text(stamp) == "NARROW MOAT"
    assert classed(_head(answers.refused_detail()), "app-moat") == []


def test_the_moat_stamp_is_outlined_in_ink_muted_with_no_fill() -> None:
    rule = _rule(".app-moat {")
    assert "color: var(--ink-muted);" in rule
    assert "background: none;" in rule
    assert "border: 1px solid currentColor;" in rule
    assert "--phase" not in rule


def test_the_change_carries_its_sign_and_no_colour_class() -> None:
    """The day's change and its percent, each with its sign, the percent to two decimals; one
    class whichever way the price moved, in the text's own colour."""
    [up] = classed(_head(answers.DETAIL), "app-company__change")
    assert text(up) == "+$2.15 (+1.19%)"
    down = QUOTE | {"change": -1.4, "changePercent": -0.7616}
    [fell] = classed(_head(answers.DETAIL, down), "app-company__change")
    assert text(fell) == "−$1.40 (−0.76%)"
    assert up["props"]["className"] == fell["props"]["className"] == "figure app-company__change"
    assert _rule(".app-company__change {") == "color: var(--ink-muted);"
    for name in _classes(_head(answers.DETAIL)) + _classes(_head(answers.DETAIL, down)):
        assert not re.search(r"up|down|positive|negative|gain|loss|green|red", name), name


def test_no_change_where_the_quote_is_not_the_snapshot_s_price() -> None:
    """The change is the quote's, so it is drawn only beside the price it is the change of: none
    where the quote's price is another, without a quote, without the change, and before a tab's
    answer is in."""
    for quote in (
        QUOTE | {"price": 180.25},
        QUOTE | {"price": None},
        QUOTE | {"change": None},
        QUOTE | {"changePercent": None},
        {"price": None, "change": None, "changePercent": None, "day": None},
        None,
    ):
        assert classed(_head(answers.DETAIL, quote), "app-company__change") == []
    unpriced = answers.detail()
    unpriced["result"] |= {"price": None}
    assert classed(_head(unpriced, QUOTE | {"price": None}), "app-company__change") == []


def test_the_head_s_controls() -> None:
    """At the right of the head, after the quote: Watchlists ▾, then Request research as the
    report page draws it, with the open item's line."""
    item = {
        "id": 5,
        "state": "pending",
        "mode": "full report",
        "claimedBy": None,
        "createdAt": "2026-11-16T09:59:00+00:00",
        "launch": None,
    }
    detail = answers.detail(item=item, launchReady=True)
    tree = _head(detail)
    [actions] = classed(tree, "app-company__actions")
    watch, request = actions["props"]["children"]
    assert watch is _button(actions, "Watchlists ▾")
    # in the look of Request research's button: the default variant and size
    assert "variant" not in watch["props"] and "size" not in watch["props"]
    ask = node("asking", [answers.SYMBOL])
    assert request == node("requestResearch", [ask, item, None, None, True])
    assert _button(request, "Request research")["props"]["disabled"] is True  # an item is open
    assert "Requested · pending" in text(request)
    [quote] = classed(tree, "app-company__quote")
    _drawn_in_order(tree, quote, watch, request)


def test_the_watchlists_button_opens_the_screen_s_popup_under_itself() -> None:
    """The popup the screen's mark opens, for this company, under the button: ``watch`` takes
    the element to open it under, else the mark a click landed on."""
    head = _function(_static_file("company.js"), "head")
    assert "P.watch({ ticker: r.symbol }, event.currentTarget);" in head
    watch = _function(_static_file("app.js"), "watch")
    assert watch.startswith("  function watch(row, mark) {")
    assert "var anchor = mark || pressedMark;" in watch


def test_the_menus_of_the_head_open_inside_the_page() -> None:
    """Request research's menu opens from its button's right edge, the button standing at the
    page's right; its error and the open item's line take a line of their own under the
    buttons."""
    assert "left: auto; right: 0;" in _rule(".app-company__actions .app-request .fb-menu {")
    assert "flex-basis: 100%;" in _rule(".app-company__actions > p {")


# ------------------------------------------------------------------------- the tabs and the date


def test_the_tabs_and_the_data_date() -> None:
    """Overview and Estimates are tabs, the open one selected; Research is a plain link to the
    report page, its symbol encoded; the data date stands at the row's right end."""
    tree = _page("tabs", "BRK.B", "estimates", "2026-11-14")
    tabs = classed(tree, "app-company__tab")
    assert [text(t) for t in tabs] == ["Overview", "Estimates", "Research"]
    overview, estimates, research = tabs
    for tab, selected in ((overview, "false"), (estimates, "true")):
        assert tab["type"] == "button"
        assert tab["props"]["role"] == "tab"
        assert tab["props"]["aria-selected"] == selected
    assert research["type"] == "a"
    assert research["props"]["href"] == "#report/BRK.B"
    assert "role" not in research["props"]
    [asof] = classed(tree, "app-company__asof")
    assert text(asof) == "data 14 Nov 2026"
    _texts_in_order(tree, "Overview", "Estimates", "Research", "data 14 Nov 2026")

    other = _page("tabs", "A&B", "overview", None)
    assert [t["props"].get("aria-selected") for t in classed(other, "app-company__tab")] == [
        "true",
        "false",
        None,
    ]
    assert classed(other, "app-company__tab")[2]["props"]["href"] == "#report/A%26B"
    assert classed(other, "app-company__asof") == []


def test_a_tab_replaces_the_hash_and_research_adds_an_entry() -> None:
    """A tab opens through ``show``, which replaces the hash, so the browser's Back never steps
    through the tabs; Research is a link, which adds an entry."""
    tabs = _function(_static_file("company.js"), "tabs")
    assert "onClick: function () { P.show('company', symbol, t[0]); }" in tabs
    assert "href: '#report/' + encodeURIComponent(symbol)" in tabs


# ------------------------------------------------------------------------------ the formatters


@pytest.mark.parametrize(
    ("helper", "args", "shown"),
    [
        ("money", [{"value": 356.27, "currency": "USD"}], "$356.27"),
        ("money", [{"value": 1507.85, "currency": "USD"}], "$1,507.85"),
        ("money", [{"value": 120, "currency": "TWD"}], "TWD 120.00"),
        ("money", [{"value": -1.2, "currency": "USD"}], "−$1.20"),
        ("money", [{"value": -0.001, "currency": "USD"}], "$0.00"),
        ("money", [None], "—"),
        ("big", [{"value": 5.18e12, "currency": "USD"}], "$5.18T"),
        ("big", [{"value": 4.94e12, "currency": "TWD"}], "TWD 4.94T"),
        ("big", [{"value": 478.8e9, "currency": "USD"}], "$478.8B"),
        ("big", [14.53e9], "14.53B"),
        ("big", [39.1e6], "39.1M"),
        ("big", [167000], "167,000"),
        ("big", [{"value": -2.5e9, "currency": "TWD"}], "−TWD 2.50B"),
        ("big", [None], "—"),
        ("big", [{"value": None, "currency": "USD"}], "—"),
        ("percent", [0.4879], "48.8%"),
        ("percent", [0.0137, 2], "1.37%"),
        ("percent", [-0.0533], "−5.3%"),
        ("percent", [None], "—"),
        ("points", [88.42], "88.4%"),
        ("points", [1.1928, 2], "1.19%"),
        ("points", [None], "—"),
        ("signed", ["$1.39", 1.39], "+$1.39"),
        ("signed", ["$1.39", -1.39], "−$1.39"),
        ("signed", ["0.0%", 0.01], "0.0%"),
        ("signed", ["—", None], "—"),
        ("multiple", [39.3], "39.3x"),
        ("multiple", [0], "—"),
        ("multiple", [None], "—"),
        ("day", ["2026-11-13"], "13 Nov 2026"),
        ("day", [None], "—"),
        ("count", [167000], "167,000"),
        ("count", [None], "—"),
    ],
)
def test_the_formatters(helper: str, args: list[Any], shown: str) -> None:
    """Money to cents, a currency other than the US dollar by its code; large amounts compact; a
    fraction or a percent as given to one decimal unless told; a sign on a change that is not
    zero at its precision; a multiple's x, and a dash at 0; a date in words; a count grouped. A
    missing figure is the dash."""
    assert _page(helper, *args) == shown


# ------------------------------------------------------------------------ the blocks' helpers


def test_a_panel_a_list_of_pairs_a_group_and_a_table() -> None:
    rows = [["Market cap", "$412.6B"], ["Sector", "Technology", True]]
    kv = _page("kv", rows)
    assert kv["props"]["className"] == "app-kv"
    pairs = classed(kv, "app-kv__row")
    assert [[text(e) for e in classed(row, "app-kv__k")] for row in pairs] == [
        ["Market cap"],
        ["Sector"],
    ]
    values = [classed(row, "app-kv__v")[0]["props"]["className"] for row in pairs]
    assert values == ["figure app-kv__v", "body app-kv__v"]

    group = _page("group", "Size", rows)
    [title] = classed(group, "app-company__grouptitle")
    assert title["type"] == "h3" and text(title) == "Size"
    assert "label" in title["props"]["className"].split()
    assert classed(group, "app-kv") != []

    table = _page("table", ["", "3Y"], [["Revenue", "25.0%"]])
    assert table["type"] == "table"
    assert [text(e) for e in elements(table) if e["type"] == "th"] == ["", "3Y"]
    cells = [e for e in elements(table) if e["type"] == "td"]
    assert [c["props"]["className"] for c in cells] == ["body app-company__rowname", "figure"]

    panel = _page("panel", "Company", None, ["inside"])
    assert panel["type"] == "section"
    assert panel["props"]["className"] == "app-company__panel"
    [title] = [e for e in elements(panel) if e["type"] == "h2"]
    assert text(title) == "Company"
    assert "inside" in text(panel)


def test_the_tabs_draw_from_the_functions_later_scripts_hang_on_draw() -> None:
    """``draw`` starts empty; under the tabs the page draws the open tab's function on its answer
    and the detail, and nothing while it is missing; a tab's failed read draws its sentence."""
    script = _static_file("company.js")
    body = _function(script, "tabBody")
    _in_order(
        body,
        "if (state.failed) return note(state.failed);",
        "var drawn = P.companyPage.draw[state.tab];",
        "return answer && drawn ? drawn(answer, d) : null;",
    )
    assert "draw: {}" in script


# -------------------------------------------------------------------------------- the reads


def test_the_reads_and_their_failures() -> None:
    """The detail, then the open tab's read; the page shown stays, faded, until the new one
    lands, and the latest read wins; a tab's failed read draws one sentence, the detail's its
    own and the link back."""
    script = _static_file("company.js")
    load = _function(script, "load")
    _in_order(
        load,
        "var want = P.company;",
        "var request = ++latest;",
        "if (state.request && state.request.symbol !== want.symbol) P.stopLaunch(state.request);",
        "state.loading = true;",
        "(whole ? read(company) : Promise.resolve(state.detail))",
        "read(company + '/page/' + want.tab)",
        ".then(function (found) {\n        if (request !== latest) return;",
        "P.followItem(asked(want.symbol), found.detail.item, render, load);",
        ".catch(function (err) {\n        if (request !== latest) return;",
        "state.error = err.message;",
    )
    assert "'The company\\'s data did not load: ' + err.message +" in load
    assert "'. Open the page again to retry.'" in load
    page = _function(script, "page")
    assert "state.loading ? 'app-company is-loading' : 'app-company'" in page
    _in_order(page, "if (state.error) {", "back(), note(state.error)")
    back = _function(script, "back")
    assert "P.show('screen');" in back and "'Back to the screen'" in back
    assert "P.onShow.company = load;" in script
    assert _rule(".app-company.is-loading {") == "opacity: 0.5;"


# ------------------------------------------------------------------------------ the address


def test_the_view_is_one_of_controls_js_s() -> None:
    """``company`` joins the views, with its panel and its script after charts.js; no header view
    names it. Its hash takes a symbol and a tab, which ``fromHash`` hands ``show``; without a
    symbol it is the Screen."""
    js = _static_file("controls.js")
    views = re.search(r"\n  var VIEWS = \[(.*?)\];", js, re.DOTALL)
    assert views is not None and "company" in re.findall(r"'(\w+)'", views.group(1))
    show = _function(js, "show")
    _in_order(
        show,
        "if (VIEWS.indexOf(tab) === -1 || ((tab === 'report' || tab === 'company') && !section)) {",
        "tab = 'screen';",
        "(tab === 'company' && keepCompany(section, id));",
        "(tab === 'company' ? companyPath() : '')",
        "if (P.onShow[tab]) P.onShow[tab]();",
    )
    assert "show(parts[0], parts[1], parts[2]);" in _function(js, "fromHash")
    assert "view: state.tab === 'report' || state.tab === 'company' ? '' : state.tab," in js
    assert "P.company = null;" in js
    html = _static_file("index.html")
    assert '<section id="company" hidden></section>' in html
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert scripts.index("company.js") == scripts.index("charts.js") + 1
    rule = _rule("#company {")
    assert "overflow: auto;" in rule and "flex: 1;" in rule


def test_the_symbol_is_coded_as_the_report_page_codes_it() -> None:
    """Decoded and upper-cased where the hash is read, encoded where the hash is written, in
    keepCompany and companyPath as in keepReport and reportPath."""
    js = _static_file("controls.js")
    for keep, path in (("keepReport", "reportPath"), ("keepCompany", "companyPath")):
        assert "decodeURIComponent(symbol)" in _function(js, keep)
        assert "toUpperCase()" in _function(js, keep)
        assert "encodeURIComponent(P." in _function(js, path)


def test_the_hash_both_ways() -> None:
    """keepCompany and companyPath run in node on hashes as a link writes them: the symbol
    decoded and upper-cased, an unknown tab the Overview, and the hash written back with the
    symbol encoded and no tab for the Overview. True when the company or the tab moved."""
    js = _static_file("controls.js")
    tabs = re.search(r"\n  (var COMPANY_TABS = .*?;)\n", js)
    assert tabs is not None
    source = "\n".join(
        [
            "var P = {};",
            tabs.group(1),
            _function(js, "keepCompany") + "\n  }",
            _function(js, "companyPath") + "\n  }",
            "var out = [];",
            "for (const [symbol, tab] of JSON.parse(process.argv[1])) {",
            "  const moved = keepCompany(symbol, tab);",
            "  out.push([moved, P.company, companyPath()]);",
            "}",
            "process.stdout.write(JSON.stringify(out));",
        ]
    )
    hashes = [
        ["brk.b", "estimates"],
        ["BRK.B", "estimates"],
        ["BRK%2EB", None],
        ["BRK.B", "financials"],
        ["A%26B", "overview"],
        ["%E0%A4%A", "estimates"],
    ]
    assert NODE is not None
    done = subprocess.run(
        [NODE, "-e", source, json.dumps(hashes)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert json.loads(done.stdout) == [
        [True, {"symbol": "BRK.B", "tab": "estimates"}, "/BRK.B/estimates"],
        [False, {"symbol": "BRK.B", "tab": "estimates"}, "/BRK.B/estimates"],
        [True, {"symbol": "BRK.B", "tab": "overview"}, "/BRK.B"],
        [False, {"symbol": "BRK.B", "tab": "overview"}, "/BRK.B"],
        [True, {"symbol": "A&B", "tab": "overview"}, "/A%26B"],
        [True, {"symbol": "%E0%A4%A", "tab": "estimates"}, "/%25E0%25A4%25A/estimates"],
    ]
