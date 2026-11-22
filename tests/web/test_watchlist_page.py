"""The watchlist page (spec 2026-11-22): one list drawn by the Screen's own table and drawer."""

from typing import Any

import pytest
from support.page import NODE, STATIC, node
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
