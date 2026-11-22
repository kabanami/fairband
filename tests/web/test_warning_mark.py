"""The warnings mark and the hover on a mechanical value (spec 2026-11-19 7.5 and 9), the screen's
part: in the Mechanical column, a cell with a value carries the hover, the count of the row's
quality warnings and their plain words, then the note, or the note alone; the mark, the bullet of
IBM Plex Mono enlarged (form A of the look), stands before the figure of a marked row, as an image
whose name is the hover's first sentence; the column's head carries the note. A refused row's em
dash has neither. The hover, the mark and the head's note are ``fairband:`` patches of the vendored
bundle, ScreenTable's ``mechanicalNote``; without it the cell is drawn as it was. The Flags and
the Warnings columns have left the catalog, so a saved list that names them loses them. The
drawer's and the company page's part: BandMeter takes the hover as the title of its fair value's
marker (``fairTitle``) or of its caption (``captionTitle``), each a ``fairband:`` patch
(``tests/web/test_drawer_form.py`` and ``test_company_overview.py`` read what the page hands it).

The bundle and the page's scripts run in node (``support.page``), and the tests read the trees
ScreenTable draws; a prop written ``{"$page": <name>}`` is the page's own (``tests/web/page.mjs``),
here the screen's note, which the screen's table and each watchlist's hand ScreenTable."""

import re
from typing import Any

import pytest
from support.page import BUNDLE, NODE, classed, elements, node

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# The two notes and the hover's example, as the Words table gives them.
NOTE = (
    "Preliminary estimate only. To ask an agent for a reviewed valuation, open the company and"
    " click Request research."
)
OPEN_NOTE = (
    "Preliminary estimate only. To ask an agent for a reviewed valuation, click Request research."
)
THREE = ["heavy capital spending", "negative free cash flow", "new shares issued"]
FIRST = "3 warnings: heavy capital spending; negative free cash flow; new shares issued."
MECH = "fb-num figure fb-screen__mech"
# A valued screen row with no review, its three warnings marking its mechanical value.
ROW: dict[str, Any] = {
    "ticker": "KTLE",
    "name": "Kettle Works",
    "phase": 5,
    "fairLow": 110.0,
    "fairHigh": 136.0,
    "fairValue": 123.45,
    "buyLevel": 100.0,
    "trimLevel": 160.0,
    "price": 131.2,
    "mechanical": 123.45,
    "reviewed": None,
    "warnings": THREE,
    "marked": True,
}
# The mark as the bundle draws it for ROW.
MARK: dict[str, Any] = {
    "type": "span",
    "props": {"className": "fb-warnmark", "role": "img", "aria-label": FIRST, "children": ["•"]},
}


def _table(rows: list[dict[str, Any]], **props: Any) -> Any:
    """ScreenTable on ``rows`` with ``props``, its bar off."""
    return node("Fairband.ScreenTable", [{"rows": rows, "chooser": False, **props}])


def _screen(rows: list[dict[str, Any]]) -> Any:
    """ScreenTable on ``rows`` as the screen and each watchlist hand it the note: the page's own."""
    return _table(rows, mechanicalNote={"$page": "SCREEN_NOTE"})


def _cells(tree: Any) -> list[dict[str, Any]]:
    """The Mechanical cells, one a row, in the rows' order."""
    return [
        e for e in elements(tree) if e.get("type") == "td" and e["props"].get("className") == MECH
    ]


def _head(tree: Any, key: str) -> dict[str, Any]:
    [head] = [e for e in elements(tree) if e.get("type") == "th" and e["props"]["data-key"] == key]
    return head


def test_the_hover_s_three_forms() -> None:
    """The note alone for no warning; "1 warning: …" for one; "3 warnings: …" for three, their
    words joined by a semicolon in the row's order, a full stop, a space, then the note. The page
    holds the two notes, the screen's and the open company's, in the Words table's words."""
    assert node("Fairband.warningsHover", [[], NOTE]) == NOTE
    assert node("Fairband.warningsHover", [["one-time items"], NOTE]) == (
        "1 warning: one-time items. " + NOTE
    )
    assert node("Fairband.warningsHover", [THREE, NOTE]) == (
        "3 warnings: heavy capital spending; negative free cash flow; new shares issued. " + NOTE
    )
    assert node("Fairband.warningsHover", [THREE, OPEN_NOTE]) == FIRST + " " + OPEN_NOTE
    assert node("SCREEN_NOTE", []) == NOTE
    assert node("OPEN_NOTE", []) == OPEN_NOTE


def test_the_mark_is_the_bullet_with_its_label() -> None:
    """The bullet U+2022, an image whose name is the hover's first sentence, as the coverage mark
    after a ticker is; no title of its own and no control: the cell's title is its hover."""
    assert node("Fairband.WarningMark", [{"words": THREE}]) == MARK
    one = node("Fairband.WarningMark", [{"words": ["one-time items"]}])
    assert one["props"]["aria-label"] == "1 warning: one-time items."
    assert one["props"]["children"] == ["•"]


def test_a_marked_row_s_cell() -> None:
    """A marked row's cell has the hover as its title, its first child the mark, then the figure;
    the watchlists' table, handed the same note, draws the same cell."""
    [cell] = _cells(_screen([ROW]))
    assert cell == {
        "type": "td",
        "props": {
            "className": MECH,
            "title": FIRST + " " + NOTE,
            "children": [MARK, "$123.45"],
        },
    }
    [listed] = _cells(_table([ROW | {"watched": True}], dense=True, mechanicalNote=NOTE))
    assert listed == cell


def test_a_row_under_the_cut_off_keeps_the_hover_alone() -> None:
    """A valued row the server does not mark keeps the hover and draws no mark: two warnings under
    the cut-off, one, none (the note alone), and a reviewed row with three, whose value an agent
    has looked at."""
    two = ROW | {"warnings": THREE[:2], "marked": False}
    one = ROW | {"ticker": "ONE", "warnings": ["one-time items"], "marked": False}
    none = ROW | {"ticker": "NONE", "warnings": [], "marked": False}
    reviewed = ROW | {"ticker": "RVWD", "reviewed": 140.0, "marked": False}
    cells = _cells(_screen([two, one, none, reviewed]))
    assert [c["props"]["title"] for c in cells] == [
        "2 warnings: heavy capital spending; negative free cash flow. " + NOTE,
        "1 warning: one-time items. " + NOTE,
        NOTE,
        FIRST + " " + NOTE,
    ]
    assert [c["props"]["children"] for c in cells] == [[None, "$123.45"]] * 4
    assert classed(_screen([two, one, none, reviewed]), "fb-warnmark") == []
    # a row the server sends without the fields reads as one with no warning
    bare = {k: v for k, v in ROW.items() if k not in ("warnings", "marked")}
    [cell] = _cells(_screen([bare]))
    assert (cell["props"]["title"], cell["props"]["children"]) == (NOTE, [None, "$123.45"])


def test_a_refused_row_s_dash_has_no_hover_and_no_mark() -> None:
    """A refused row keeps its warnings' words but has no value: its em dash has no title and no
    mark, even if a row came marked; a placeholder's is the same."""
    refused = ROW | {"mechanical": None, "marked": False}
    stray = ROW | {"ticker": "STRY", "mechanical": None}
    placeholder = {
        "ticker": "PLHD",
        "name": None,
        "phase": None,
        "fairLow": None,
        "fairHigh": None,
        "price": None,
        "mechanical": None,
        "reviewed": None,
        "warnings": [],
        "marked": False,
    }
    dash = {"type": "td", "props": {"className": MECH, "children": ["—"]}}
    assert _cells(_screen([refused, stray, placeholder])) == [dash, dash, dash]


def test_the_mechanical_head_carries_the_note() -> None:
    """Given the note, the Mechanical head's title is the note; no other head has one. Without the
    note no head has a title."""
    noted = _screen([ROW])
    assert _head(noted, "mechanical")["props"]["title"] == NOTE
    heads = [e for e in elements(noted) if e.get("type") == "th"]
    assert [h["props"]["data-key"] for h in heads if h["props"].get("title")] == ["mechanical"]
    plain = [e for e in elements(_table([ROW])) if e.get("type") == "th"]
    assert plain and all(h["props"].get("title") is None for h in plain)


def test_without_the_prop_the_cell_is_as_before() -> None:
    """Without mechanicalNote the cell is the figure alone, a marked row's too: no title, no
    mark."""
    assert _cells(_table([ROW, ROW | {"ticker": "RFSD", "mechanical": None}])) == [
        {"type": "td", "props": {"className": MECH, "children": ["$123.45"]}},
        {"type": "td", "props": {"className": MECH, "children": ["—"]}},
    ]
    assert classed(_table([ROW]), "fb-warnmark") == []


def test_the_meter_takes_the_two_titles() -> None:
    """BandMeter's ``fairTitle`` is the title of the fair value's marker on the track and its
    ``captionTitle`` the title of the caption: the drawer and the company page hand it the hover
    of the mechanical value, the one on a row with no review, the other on a reviewed row. Without
    them neither has a title, and the meter draws no mark of its own."""
    hover = FIRST + " " + OPEN_NOTE
    meter = {"low": 110.0, "high": 136.0, "price": 131.2, "fairValue": 123.45, "showScale": False}
    fair = node("Fairband.BandMeter", [meter | {"fairTitle": hover}])
    [marker] = classed(fair, "fb-band__fairmark")
    assert marker["props"]["title"] == hover
    assert classed(fair, "fb-band__caption") == []  # no caption without one
    captioned = node(
        "Fairband.BandMeter",
        [meter | {"caption": "mechanical $123.45", "captionTitle": hover}],
    )
    [caption] = classed(captioned, "fb-band__caption")
    assert caption == {
        "type": "div",
        "props": {
            "className": "fb-band__caption caption",
            "title": hover,
            "children": ["mechanical $123.45"],
        },
    }
    assert classed(captioned, "fb-band__fairmark")[0]["props"].get("title") is None
    plain = node("Fairband.BandMeter", [meter | {"caption": "mechanical $123.45"}])
    assert classed(plain, "fb-band__fairmark")[0]["props"].get("title") is None
    assert classed(plain, "fb-band__caption")[0]["props"].get("title") is None
    for tree in (fair, captioned, plain):
        assert classed(tree, "fb-warnmark") == []
    # the two props are declared beside the meter's others, each a fairband patch of the spec
    declarations = (BUNDLE.parent / "index.d.ts").read_text(encoding="utf-8")
    props = re.search(r"export interface BandMeterProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    for name in ("fairTitle", "captionTitle"):
        doc = props.group(1)[: props.group(1).index(f"  {name}?: string;")]
        doc = doc[doc.rindex("/**") :]
        assert "* fairband: the title of the" in doc and "(spec 2026-11-19 7.5)" in doc, name


def test_the_removed_columns_are_no_column_keys() -> None:
    """The Flags and the Warnings columns are gone from the catalog, so the chooser offers neither
    and a list that names them draws without them, as the page's normalise drops a key the catalog
    does not know. The Clean filter is gone from the empty filters."""
    keys = node("Fairband.COLUMN_KEYS", [])
    assert "flags" not in keys and "flagCount" not in keys
    assert "mechanical" in keys and "watchlists" in keys
    saved = ["ticker", "flags", "mechanical", "flagCount", "price"]
    heads = [e for e in elements(_table([ROW], columns=saved)) if e.get("type") == "th"]
    assert [h["props"]["data-key"] for h in heads] == ["ticker", "mechanical", "price"]
    assert node("Fairband.EMPTY_FILTERS", []) == {
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
