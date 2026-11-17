"""The company logo on the page (B-203): the drawer's head and the company page's head draw the
detail read's ``logo`` before the ticker, on a tile, and nothing without one. The tile is white
unless the logo's marks are light where they meet its clear ground, when it is dark (B-206).
The page's own script runs in node (``support.page``) and the tests read what ``logo`` and
``logoGround`` return; where each head calls ``logo``, what its handlers do, and the tile's style
are read from the files."""

import re

import pytest
from support.page import NODE, node
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

ROUTE = "/api/companies/AAPL/logo"
# A test image's pixels by letter, as red, green, blue and alpha: clear, white, black, red, and
# a white too faint to count as a mark.
INK = {
    ".": (0, 0, 0, 0),
    "W": (255, 255, 255, 255),
    "K": (0, 0, 0, 255),
    "R": (200, 30, 30, 255),
    "w": (255, 255, 255, 90),
}


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


def _ground(*rows: str) -> str:
    """What ``logoGround`` answers for a square image drawn in ``INK``'s letters."""
    size = len(rows)
    assert all(len(row) == size for row in rows)
    data = [channel for row in rows for letter in row for channel in INK[letter]]
    found = node("logoGround", [data, size])
    assert isinstance(found, str)
    return found


def test_light_marks_on_a_clear_ground_need_a_dark_tile() -> None:
    """Many of FMP's logos are white marks on a clear ground, drawn for a dark page, and on a
    white tile they are a plain white square. The ground is read where the marks meet the clear
    pixels: a mark's pixel beside a clear one is an edge pixel, and a logo whose edge is mostly
    light stands on a dark tile."""
    assert _ground("....", ".WW.", ".WW.", "....") == "dark"
    assert _ground("....", ".KK.", ".KK.", "....") == "white"
    assert _ground("....", ".RR.", ".RR.", "....") == "white"


def test_white_inside_a_coloured_shape_keeps_the_white_tile() -> None:
    """White lettering inside a coloured shape does not meet the ground, so it needs no dark
    tile: the shape's edge decides."""
    assert _ground("......", ".RRRR.", ".RWWR.", ".RWWR.", ".RRRR.", "......") == "white"


def test_the_larger_part_of_the_edge_decides_and_a_tie_keeps_the_white_tile() -> None:
    # three edge pixels of white, three of red: the pixel in each corner meets no clear one
    assert _ground("WW..", "WW..", "..RR", "..RR") == "white"
    # four of white, with the lone pixel, and three of red
    assert _ground("WW.W", "WW..", "..RR", "..RR") == "dark"


def test_a_faint_pixel_counts_as_clear() -> None:
    """A pixel under half opaque is the soft rim of a mark, not the mark."""
    assert _ground("....", ".Ww.", "....", "....") == "dark"
    assert _ground("wwww", "wwww", "wwww", "wwww") == "blank"


def test_an_image_with_no_clear_pixel_keeps_the_white_tile() -> None:
    """It brings its own ground, so the tile shows only as its rim."""
    assert _ground("RRR", "RRR", "RRR") == "white"
    assert _ground("WWW", "WKW", "WWW") == "white"


def test_an_image_with_no_mark_is_blank() -> None:
    """A file that is white all over, as FMP holds for some companies, or clear all over."""
    assert _ground("WWW", "WWW", "WWW") == "blank"
    assert _ground("...", "...", "...") == "blank"


def test_a_loaded_image_takes_its_ground_and_a_blank_one_is_hidden() -> None:
    """When the image loads the page reads its pixels through a canvas, 64 a side, and sets the
    tile before it shows it: ``is-on-dark`` for a dark ground. A blank image is hidden like one
    that did not load. Where the browser gives no pixels the tile stays white."""
    script = _static_file("app.js")
    loaded = _function(script, "logoLoaded")
    for part in (
        "var pixels = logoPixels(image);",
        "var ground = pixels ? logoGround(pixels, LOGO_SAMPLE) : 'white';",
        "if (ground === 'blank') { image.hidden = true; return; }",
        "if (ground === 'dark') image.classList.add('is-on-dark');",
        "image.classList.add('is-loaded');",
    ):
        assert part in loaded, part
    assert loaded.index("is-on-dark") < loaded.index("is-loaded")
    assert "var LOGO_SAMPLE = 64;" in script
    pixels = _function(script, "logoPixels")
    assert "context.getImageData(0, 0, LOGO_SAMPLE, LOGO_SAMPLE).data" in pixels
    assert "} catch (error) {" in pixels and "return null;" in pixels
    assert "onLoad: logoLoaded," in _function(script, "logo")
    assert _rule(".app-logo.is-on-dark") == "background: #121417;"


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
    assert node("logo", [{}, "app-company__logo"]) is None


def test_an_image_that_does_not_load_hides_itself() -> None:
    """A failed fetch is a 404 from the logo read, and the page shows nothing, not the browser's
    broken-image mark."""
    logo = _function(_static_file("app.js"), "logo")
    assert "onError: function (event) { event.target.hidden = true; }" in logo


def test_the_tile_shows_only_once_its_image_has_loaded() -> None:
    """The first read of a logo waits on the server's fetch, and a white tile with no image in
    it would flash on the dark theme meanwhile. The tile keeps its place, so nothing moves when
    the image lands."""
    assert "image.classList.add('is-loaded');" in _function(_static_file("app.js"), "logoLoaded")
    assert "visibility: hidden;" in _rule(".app-logo")
    assert _rule(".app-logo.is-loaded") == "visibility: visible;"


def test_each_head_draws_the_logo_before_the_ticker() -> None:
    sections = _function(_static_file("app.js"), "sections")
    head = sections[sections.index("className: 'app-drawer__head'") :]
    assert head.index("logo(body, 'app-drawer__logo'),") < head.index("app-drawer__ticker")
    company = _function(_static_file("company.js"), "head")
    assert company.index("P.logo(d, 'app-company__logo'),") < company.index("'ticker'")


def test_the_tile_is_white_in_both_themes_unless_the_logo_needs_a_dark_one() -> None:
    """Most of FMP's logos are drawn for a white ground, so the tile is white under either theme
    and reads no theme token; the dark tile (``is-on-dark``) is one colour under either theme
    too. The image keeps its shape inside the tile."""
    tile = _rule(".app-logo")
    for declaration in (
        "background: #ffffff;",
        "object-fit: contain;",
        "border-radius: var(--radius-sm);",
        "flex: none;",
    ):
        assert declaration in tile, declaration
    assert "width: 24px; height: 24px;" in tile
    assert "width: 40px; height: 40px;" in _rule(".app-company__logo")
