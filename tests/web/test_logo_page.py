"""The company logo on the page (B-203): the drawer's head and the report page's head draw the
detail read's ``logo`` before the ticker, on a white tile in both themes, and nothing without one.
The page's own script runs in node (``support.page``) and the test reads what ``logo`` returns;
where each head calls it, and the tile's style, are read from the files."""

import re

import pytest
from support.page import NODE, node
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

ROUTE = "/api/companies/AAPL/logo"


def _function(script: str, name: str) -> str:
    """The text of the script's ``function <name>(``, to its closing brace."""
    start = script.index(f"  function {name}(")
    return script[start : script.index("\n  }\n", start)]


def _rule(selector: str) -> str:
    """The declarations of the page's rule for ``selector``."""
    pattern = rf"\n  {re.escape(selector)} \{{(.*?)\}}"
    found = re.search(pattern, _static_file("index.html"), re.DOTALL)
    assert found is not None, selector
    return " ".join(found.group(1).split())


def test_the_logo_is_an_image_of_the_logo_read() -> None:
    """The image reads the address the detail read names. Its ``alt`` is empty: the ticker and
    the name stand beside it. Its key is the address, so the drawer's next company draws a new
    element, not one an earlier failed load hid."""
    drawn = node("logo", [{"logo": ROUTE}, "app-drawer__logo"])
    assert drawn["type"] == "img"
    assert drawn["props"] == {
        "key": ROUTE,
        "className": "app-logo app-drawer__logo",
        "src": ROUTE,
        "alt": "",
        "children": [],
    }


def test_a_company_without_a_logo_draws_none() -> None:
    assert node("logo", [{"logo": None}, "app-drawer__logo"]) is None
    assert node("logo", [{}, "app-report__logo"]) is None


def test_an_image_that_does_not_load_hides_itself() -> None:
    """A failed fetch is a 404 from the logo read, and the page shows nothing, not the browser's
    broken-image mark."""
    logo = _function(_static_file("app.js"), "logo")
    assert "onError: function (event) { event.target.hidden = true; }" in logo


def test_the_tile_shows_only_once_its_image_has_loaded() -> None:
    """The first read of a logo waits on the server's fetch, and a white tile with no image in
    it would flash on the dark theme meanwhile. The tile keeps its place, so nothing moves when
    the image lands."""
    logo = _function(_static_file("app.js"), "logo")
    assert "onLoad: function (event) { event.target.classList.add('is-loaded'); }" in logo
    assert "visibility: hidden;" in _rule(".app-logo")
    assert _rule(".app-logo.is-loaded") == "visibility: visible;"


def test_each_head_draws_the_logo_before_the_ticker() -> None:
    sections = _function(_static_file("app.js"), "sections")
    head = sections[sections.index("className: 'app-drawer__head'") :]
    assert head.index("logo(body, 'app-drawer__logo'),") < head.index("app-drawer__ticker")
    report = _function(_static_file("report.js"), "head")
    assert report.index("P.logo(d, 'app-report__logo'),") < report.index("app-report__ticker")


def test_the_logo_stands_on_a_white_tile_in_both_themes() -> None:
    """FMP's logos are drawn for a white ground, many dark on a clear one, so the tile is white
    under either theme and reads no theme token; the image keeps its shape inside it."""
    tile = _rule(".app-logo")
    for declaration in (
        "background: #ffffff;",
        "object-fit: contain;",
        "border-radius: var(--radius-sm);",
        "flex: none;",
    ):
        assert declaration in tile, declaration
    assert "width: 24px; height: 24px;" in tile
    assert "width: 32px; height: 32px;" in _rule(".app-report__logo")
    assert "align-self: center;" in _rule(".app-report__logo")
