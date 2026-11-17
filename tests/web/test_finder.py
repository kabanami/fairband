"""The header's finder (the company page's design, the founder's rulings of 2026-11-17): a field in
the header's right slot, on every view but the Screen, whose table has its own, that opens a
company's page. It matches as the Screen's field does, a ticker that starts with the text or a
name that holds it, on the rows the page already holds, and lists eight at most: the ticker that
is the text first, then the tickers that start with it, the names that start with it and the names
that hold it, the larger company first within each. The arrow keys move the mark, Enter opens the
marked company, Escape empties the field. The page's own scripts run in node after the bundle
(``support.page``); the tests read what ``finder.matches``, ``finder.step``, ``finder.list`` and
``finder.view`` return, and the shell's handlers and the styles as text."""

import re
from typing import Any

import pytest
from support.page import NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

FINDER = STATIC / "finder.js"


def _row(ticker: str, name: str | None, cap: float | None = 1e9) -> dict[str, Any]:
    return {"ticker": ticker, "name": name, "marketCap": cap}


ROWS = [
    _row("AAL", "American Airlines Group Inc.", 9e9),
    _row("AAPL", "Apple Inc.", 5e12),
    _row("APLE", "Apple Hospitality REIT, Inc.", 3e9),
    _row("A", "Agilent Technologies, Inc.", 4e10),
    _row("MAA", "Mid-America Apartment Communities, Inc.", 2e10),
    _row("PAPL", "Pineapple Financial Inc.", 1e8),
    _row("AA", "Alcoa Corporation", 1e10),
    _row("NONAME", None, 5e8),
]


def _matches(query: Any, rows: Any = ROWS) -> list[str]:
    return [row["ticker"] for row in node("finder.matches", [rows, query], FINDER)]


def _rule(selector: str) -> str:
    """The declarations of ``selector``'s own rule in the page's stylesheet."""
    found = re.search(
        r"^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", _static_file("index.html"), re.MULTILINE
    )
    assert found is not None, selector
    return " ".join(found.group(1).split())


def test_a_ticker_that_starts_with_the_text_or_a_name_that_holds_it_matches_as_on_the_screen() -> (
    None
):
    """The Screen's field (``narrow``, app.js): the ticker starts with the text, or the name holds
    it. PAPL holds ``apl`` in its ticker and not in its name, so it does not match; a row with no
    name matches by its ticker alone."""
    assert _matches("aa") == ["AA", "AAPL", "AAL"]
    assert _matches("apl") == ["APLE"]
    assert _matches("non") == ["NONAME"]
    assert _matches("zzz") == []


def test_the_exact_ticker_leads_then_ticker_starts_name_starts_and_name_holds() -> None:
    """``a``: the ticker A itself; then the tickers that start with it, the largest first; then the
    names that start with it and are not already listed; then the names that only hold it."""
    assert _matches("a") == ["A", "AAPL", "AA", "AAL", "APLE", "MAA", "PAPL"]
    assert _matches("apple") == ["AAPL", "APLE", "PAPL"]
    assert _matches("apartment") == ["MAA"]


def test_the_text_is_trimmed_and_its_case_does_not_matter() -> None:
    assert _matches("  AaPl ") == ["AAPL"]
    assert _matches("APPLE INC") == ["AAPL"]


def test_nothing_typed_and_no_rows_match_nothing() -> None:
    assert _matches("") == []
    assert _matches("   ") == []
    assert _matches(None) == []
    assert _matches("a", None) == []
    assert _matches("a", []) == []


def test_eight_matches_at_most_and_equal_companies_in_ticker_order() -> None:
    rows = [_row(f"T{n:02d}", "Twelve Trees Corp.", None) for n in range(12)]
    assert _matches("t", rows) == [f"T{n:02d}" for n in range(8)]
    assert _matches("twelve", list(reversed(rows))) == [f"T{n:02d}" for n in range(8)]


@pytest.mark.parametrize(
    ("count", "active", "key", "expected"),
    [
        (3, 0, "ArrowDown", {"active": 1}),
        (3, 2, "ArrowDown", {"active": 0}),
        (3, 0, "ArrowUp", {"active": 2}),
        (3, 1, "ArrowUp", {"active": 0}),
        (3, 1, "Enter", {"go": 1}),
        (0, 0, "Enter", None),
        (0, 0, "ArrowDown", None),
        (3, 1, "Escape", {"close": True}),
        (0, 0, "Escape", {"close": True}),
        (3, 1, "a", None),
        (3, 1, "Tab", None),
    ],
)
def test_a_key_moves_the_mark_opens_the_marked_company_or_closes_the_list(
    count: int, active: int, key: str, expected: dict[str, Any] | None
) -> None:
    """The arrows turn round at the list's ends; Enter on an empty list does nothing; any other
    key is the field's own."""
    assert node("finder.step", [count, active, key], FINDER) == expected


def test_the_list_draws_each_company_its_ticker_and_its_name_and_marks_one() -> None:
    found = node("finder.matches", [ROWS, "apple"], FINDER)
    tree = node("finder.list", [found, 1], FINDER)
    assert tree["type"] == "ul"
    assert tree["props"]["id"] == "app-finder-list" and tree["props"]["role"] == "listbox"
    assert tree["props"]["className"].split() == ["fb-menu", "app-finder__list"]
    options = [e for e in elements(tree) if e["props"].get("role") == "option"]
    assert [o["props"]["id"] for o in options] == [f"app-finder-opt-{n}" for n in range(3)]
    assert [o["props"]["aria-selected"] for o in options] == ["false", "true", "false"]
    assert [text(classed(o, "ticker")) for o in options] == ["AAPL", "APLE", "PAPL"]
    assert [text(classed(o, "app-finder__name")) for o in options] == [
        "Apple Inc.",
        "Apple Hospitality REIT, Inc.",
        "Pineapple Financial Inc.",
    ]


def test_a_company_with_no_name_draws_its_ticker_alone() -> None:
    tree = node("finder.list", [[_row("NONAME", None)], 0], FINDER)
    assert tree["props"]["aria-label"] == "Companies"
    [option] = [e for e in elements(tree) if e["props"].get("role") == "option"]
    assert text(option) == "NONAME" and classed(option, "app-finder__name") == []


@pytest.mark.parametrize(
    ("note", "words"),
    [(None, "No company matches"), ("The companies have not loaded.",) * 2],
)
def test_an_empty_list_says_why_in_one_row_that_cannot_be_picked(
    note: str | None, words: str
) -> None:
    """Nothing found, or the rows not yet in: one row with the sentence, an option of the list so
    a reader that cannot see it hears it, disabled and never selected, with no handler."""
    tree = node("finder.list", [[], 0, None, note], FINDER)
    [row] = [e for e in elements(tree) if e["type"] == "li"]
    assert text(row) == words
    assert row["props"]["className"] == "caption app-finder__none"
    assert row["props"]["role"] == "option" and row["props"]["aria-disabled"] == "true"
    assert row["props"]["aria-selected"] == "false"
    assert "onMouseDown" not in row["props"]


def test_the_field_at_rest_is_a_closed_combobox_with_the_screens_words() -> None:
    """Before anything is typed: the field alone, named for a reader that cannot see it, with the
    placeholder of the Screen's field and no list."""
    tree = node("finder.view", [{}], FINDER)
    assert tree["props"]["className"] == "app-finder"
    [field] = [e for e in elements(tree) if e["type"] == "input"]
    props = field["props"]
    assert props["placeholder"] == "Ticker or company" and props["aria-label"] == "Find a company"
    assert props["role"] == "combobox" and props["aria-expanded"] == "false"
    assert props["aria-autocomplete"] == "list"
    assert props.get("aria-controls") is None  # the list is not on the page while closed
    assert props["value"] == "" and props.get("aria-activedescendant") is None
    assert classed(tree, "app-finder__list") == []


def test_the_shell_opens_the_page_through_the_hash_and_keeps_the_field_on_a_press() -> None:
    """Read as text, since node runs the shell's first state alone: a pick sets the hash to the
    company's page as the ticker's link names it, so the browser's Back returns to the view left;
    a press of the main button on a row picks it and does not take the focus from the field, and
    another button picks nothing; a blur closes the list; a key of a text being composed is the
    text's own; the mark stays on the list when the rows change under it; while the rows are not
    in the list says so, and looks for them again shortly until they are; the list is named to
    the field only while it is on the page."""
    script = _static_file("finder.js")
    for line in (
        "window.location.hash = P.companyHref(row);",
        "if (event.button) return; /* the main button alone picks */",
        "onBlur: close",
        "if (event.nativeEvent && event.nativeEvent.isComposing) return;",
        "var found = state.open ? matches(rows, state.query) : [];",
        "var active = Math.min(state.active, Math.max(found.length - 1, 0));",
        "var does = state.open ? step(found.length, active, event.key) : null;",
        "'aria-controls': state.open ? 'app-finder-list' : null,",
        "rows ? null : 'The companies have not loaded.'",
        "if (rows || !state.open) return undefined;",
    ):
        assert line in script, line


def test_the_finder_finds_the_rows_the_screens_field_finds() -> None:
    """One function says whether a row is found, for the Screen's field and for the finder
    (``finds``, app.js), so the two cannot drift apart: the finder ranks the rows it accepts."""
    for query in ("a", "apple", "apl"):
        on_the_screen = {row["ticker"] for row in ROWS if node("finds", [row, query])}
        assert set(_matches(query)) == on_the_screen, query
    assert "if (!P.finds(row, needle)) return;" in _static_file("finder.js")
    assert "var found = !needle || finds(r, needle);" in _static_file("app.js")


def test_the_page_loads_the_finder_before_the_script_that_draws_the_header() -> None:
    page = _static_file("index.html")
    order = [
        page.index(f'<script src="/static/{name}.js">') for name in ("app", "finder", "controls")
    ]
    assert order == sorted(order)


def test_the_finder_alone_gives_way_in_a_tight_header_and_hides_where_it_has_no_room() -> None:
    """The field is 220px and may shrink to 96px; the refresh controls beside it do not shrink,
    so their words stay on one line; under 1100px of window, where the one-line header has no
    room for the field, it is not drawn. Its list opens under its left edge."""
    assert _rule(".app-finder") == (
        "position: relative; flex: 0 1 auto; width: 220px; min-width: 96px;"
    )
    page = " ".join(_static_file("index.html").split())
    assert "@media (width < 1100px) { .app-finder { display: none; } }" in page
    assert "flex: none;" in _rule(".app-actions")
    field = _rule(".app-finder__q")
    assert "width: 100%;" in field and "box-sizing: border-box;" in field
    assert (
        "background: var(--surface-sunken);" in field and "font-family: var(--font-mono);" in field
    )
    listed = _rule(".app-finder__list")
    assert "left: 0;" in listed and "right: auto;" in listed and "list-style: none;" in listed
    assert "background: var(--surface-hover);" in _rule(
        '.app-finder__opt[aria-selected="true"], .app-finder__opt:hover'
    )
