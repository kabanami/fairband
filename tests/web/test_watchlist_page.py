"""The watchlist page (spec 2026-11-22): one list drawn by the Screen's own table and drawer."""

from typing import Any

import pytest
from support.page import NODE, STATIC, elements, node, text
from support.web import _component_file, _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

WATCHLISTS = STATIC / "watchlists.js"
EMPTY: dict[str, Any] = {
    "designation": [],
    "stance": [],
    "phase": [],
    "cap": [],
    "sector": [],
    "industry": [],
    "watchlist": [],
    "reviewedOnly": False,
    "hideExpired": False,
}
GONE = {
    "name": None,
    "price": None,
    "mechanical": None,
    "reviewed": None,
    "phase": None,
    "fairLow": None,
    "fairHigh": None,
    "watched": True,
}
LISTS = [
    {
        "id": 4,
        "name": "Core",
        "createdAt": "2026-11-20T10:00:00+00:00",
        "count": 2,
        "symbols": [
            {"symbol": "AAPL", "addedAt": "2026-11-20T10:00:00+00:00"},
            {"symbol": "MSFT", "addedAt": "2026-11-20T10:00:00+00:00"},
        ],
    },
    {"id": 2, "name": "Mag7", "createdAt": "2026-11-22T10:00:00+00:00", "count": 0, "symbols": []},
]


def _function(script: str, name: str) -> str:
    """The text of the script's ``function <name>(``, to its closing brace."""
    start = script.index(f"  function {name}(")
    return script[start : script.index("\n  }\n", start)]


def _buttons(tree: Any) -> list[dict[str, Any]]:
    """The design system's Buttons in a helper's tree, in order. The harness draws no component in
    a helper's tree, so a Button stays the element it was given, with no ``type`` (JSON drops its
    function) and its own props, ``size`` among them, as ``tests/web/test_inbox_launch.py`` reads
    one."""
    return [e for e in elements(tree) if "type" not in e and "size" in e["props"]]


def _row(ticker: str, **more: Any) -> dict[str, Any]:
    return {"ticker": ticker, "name": f"{ticker} Holdings", "phase": 4, "price": 10.0} | more


def _listed() -> list[dict[str, Any]]:
    rows = [_row("MSFT"), _row("AAPL"), _row("ZZZZ")]
    listed: list[dict[str, Any]] = node("listRows", [rows, ["AAPL", "QQQQ", "MSFT", "BBBB"]])
    return listed


def test_a_lists_rows_keep_the_servers_order_then_the_symbols_with_no_row() -> None:
    listed = _listed()
    assert [r["ticker"] for r in listed] == ["MSFT", "AAPL", "BBBB", "QQQQ"]
    assert all(r["watched"] is True for r in listed)
    assert listed[2] == {"ticker": "BBBB"} | GONE


def test_find_reaches_a_symbol_with_no_row_and_no_filter_does() -> None:
    listed = _listed()
    assert [r["ticker"] for r in node("narrow", [listed, "bb", EMPTY])] == ["BBBB"]
    by_phase = node("narrow", [listed, "", EMPTY | {"phase": [4]}])
    assert [r["ticker"] for r in by_phase] == ["MSFT", "AAPL"]


def test_the_table_draws_a_list_with_its_own_find_filters_and_sort() -> None:
    app = _static_file("app.js")
    for pin in (
        "listRows: listRows, onList: onList, selectList: selectList,",
        "function shown() { return state.onList ? state.list : state; }",
        "key: state.onList ? 'list' : 'screen',",
        "listFilter: state.onList ? false : undefined,",
        "top: state.onList ? 0 : state.screenTop,",  # the Screen's place comes back with it
        "note('No companies on this list yet.')",
    ):
        assert pin in app, pin
    # the Methodology page's examples still go to the Screen's own FIND and filters
    find = app[app.index("  function find(symbol) {") :]
    find = find[: find.index("\n  }\n")]
    assert "state.query = symbol;" in find and "state.filters = F.EMPTY_FILTERS;" in find
    assert "p.listFilter === false ? [] : lists" in _component_file("bundle.js")


def test_a_failed_read_of_the_list_leaves_the_screen_its_table() -> None:
    app = _static_file("app.js")
    load_list = app[app.index("  function loadList() {") :]
    load_list = load_list[: load_list.index("\n  }\n")]
    assert "state.error" not in load_list  # the Screen keeps its table
    assert (
        "list.error = 'The list did not load: ' + err.message + '. Reload the page to try again.';"
        in load_list
    )
    # a read of the list that lands clears it, and so do equal sorts, which need no read
    assert load_list.count("list.error = null;") == 2
    render = app[app.index("  function render() {") :]
    render = render[: render.index("\n  }\n")]
    # the Screen's own failed load still shows on both views, the list's on the list alone
    assert render.index("if (state.error) {") < render.index(
        "} else if (state.onList && state.list.error) {\n      main = note(state.list.error);"
    )


@pytest.mark.parametrize(
    ("lists", "address", "default", "opened"),
    [
        (LISTS, 2, 4, 2),  # the address first
        (LISTS, 999, 2, 2),  # an address that names no list: the default
        (LISTS, None, 999, 4),  # a default that names no list: the first by name
        (LISTS, None, None, 4),
        ([], 2, 4, None),
    ],
)
def test_the_list_the_page_opens_on(
    lists: list[dict[str, Any]], address: int | None, default: int | None, opened: int | None
) -> None:
    assert node("lists.opens", [lists, address, default], WATCHLISTS) == opened


def test_the_head_has_the_selector_and_the_default_and_no_request_research() -> None:
    tree = node("lists.head", [LISTS[0], LISTS, 4], WATCHLISTS)
    [pick] = [e for e in elements(tree) if e.get("type") == "select"]
    assert pick["props"]["value"] == "4"
    options = [e for e in elements(pick) if e.get("type") == "option"]
    assert [text(o) for o in options] == ["Core (default)", "Mag7"]
    buttons = _buttons(tree)
    assert [text(b) for b in buttons] == ["Default", "Rename", "Delete"]
    assert buttons[0]["props"]["aria-pressed"] == "true"
    other = node("lists.head", [LISTS[1], LISTS, 4], WATCHLISTS)
    [first] = _buttons(other)[:1]
    assert text(first) == "Set as default" and first["props"]["aria-pressed"] == "false"
    js = _static_file("watchlists.js")
    for gone in (
        "Request research",
        "requestResearch",
        "state.requested",
        "P.openRow",
        "F.ScreenTable",
    ):
        assert gone not in js, gone


def test_the_head_follows_the_lists() -> None:
    js = _static_file("watchlists.js")
    follow = js[js.index("  function follow() {") :]
    follow = follow[: follow.index("\n  }\n")]
    for pin in (
        "if (panel.hidden) return;",
        "var lists = P.watchlists();",
        "if (lists) {",  # no list is chosen, and no address written, before the lists arrive
        "want = opens(lists, P.listId, state.defaultId);",
        "if (want !== state.selected || want !== P.listId) select(want);",
    ):
        assert pin in follow, pin
    assert "'fairband.watchlist.default'" in js
    assert "history.replaceState(null, '', '#watchlists' + (id == null ? '' : '/' + id));" in js


def test_delete_clears_a_default_it_removes() -> None:
    js = _static_file("watchlists.js")
    drop = js[js.index("  function drop(d) {") :]
    assert (
        "if (!error && d.id === state.defaultId) setDefault(null);" in drop[: drop.index("\n  }\n")]
    )


def test_show_reads_the_lists_id() -> None:
    js = _static_file("controls.js")
    for pin in (
        "var id = /^\\d+$/.test(String(word)) ? Number(word) : null;",
        "var listed = tab === 'watchlists' && keepList(section);",
        "panels[id].hidden = id !== tab && !(id === 'screen' && tab === 'watchlists');",
        "if (tab === 'screen' || tab === 'watchlists') P.onList(tab === 'watchlists');",
        "P.listId = null;",
    ):
        assert pin in js, pin


def test_the_old_view_is_gone() -> None:
    assert "function openRow(" not in _static_file("app.js")
    page = _static_file("index.html")
    assert "#watchlists .fb-screen { --bar-height: 0px; }" not in page
    assert "#groups, #methodology, #settings, #inbox { overflow: auto; }" in page
    assert "On a watchlist, it posts" not in _static_file("methodology.html")


def test_the_head_stands_above_the_table_and_a_row_with_no_name_shows_a_dash() -> None:
    """The head's panel, its own height, stands above the Screen's, which holds the table and the
    drawer under it on the watchlist page; a company with no row has no name, and its Company
    cell shows an em dash as every other empty cell does."""
    page = _static_file("index.html")
    assert "#watchlists { flex: none; padding: var(--space-2) var(--space-6); }" in page
    assert page.index('<section id="watchlists" hidden></section>') < page.index(
        '<section id="screen"></section>'
    )
    assert "#screen .fb-screen__name:empty::before { content: '—'; color: var(--ink-faint); }" in (
        page
    )
    assert "#watchlists .fb-screen__name" not in page and ".app-wl__table" not in page


def test_a_steady_view_draws_nothing_more_and_the_screen_s_place_is_used_once() -> None:
    """The head names its list on every draw (P.onRender), so an unchanged list and an unchanged
    view each return before they draw; the Screen's kept place is cleared as the table mounted for
    the Screen takes it, whatever view the page shows by the time the effect runs."""
    app = _static_file("app.js")
    assert "if (id === list.id) return;" in _function(app, "selectList")
    assert "if (on === state.onList) return;" in _function(app, "onList")
    assert "if (!props.list) state.screenTop = 0;" in _function(app, "Screen")
    assert "if (!state.onList) state.screenTop = 0;" not in app
    assert "list: state.onList," in _function(app, "render")


def test_an_address_the_page_did_not_write_decides_the_list() -> None:
    """Showing the page turns the table to the list (P.onList), whose draw runs follow before the
    view's loader forgets the selection, with the list of the last visit still selected. A
    selection the address no longer names is forgotten there first, so the header's link,
    #watchlists, opens the default, not the list last shown, and #watchlists/<id> opens its
    list."""
    follow = _function(_static_file("watchlists.js"), "follow")
    assert follow.index("if (P.listId !== state.selected) state.selected = null;") < follow.index(
        "var want = state.selected;"
    )
