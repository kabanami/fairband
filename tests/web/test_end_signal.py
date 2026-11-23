"""The end signal (spec 2026-11-23 refresh experience, 4.2 and 4.8). After a run ends the page reads
its rows again and compares each with the row it held, by ticker, on the figures a row shows
(``FairbandPage.marks``, app.js): a row that differs carries the keys that changed, a price that
moved between two numbers its direction, and the comparison counts the prices and the values that
changed. ScreenTable gives each cell of a changed figure the class ``is-changed``, a grey tint
that fades to none in 1.2 seconds, and sets ▲ or ▼ before a price that moved, in ink-muted, which
fades with it. The helper and the table run in node (``tests/web/page.mjs``); the page's reads
and the status line's count are ``tests/web/test_header.py``'s, the company page's head
``tests/web/test_company_load.py``'s."""

import re
from typing import Any

import pytest
from support.page import NODE, classed, elements, node, text
from support.web import _component_file, _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# The figures a row shows that the comparison reads, at invented values.
FIGURES: dict[str, Any] = {
    "price": 48.2,
    "fairValue": 40.0,
    "fairLow": 36.0,
    "fairHigh": 44.0,
    "buyLevel": 28.0,
    "trimLevel": 54.0,
    "priceToValue": 1.21,
    "designation": "above",
    "reviewed": None,
    "mechanical": 40.0,
    "phase": 4,
}
# The table's default columns, in the order it draws them.
DEFAULT_COLUMNS = [
    "ticker",
    "name",
    "phase",
    "band",
    "mechanical",
    "reviewed",
    "price",
    "designation",
]


def row(ticker: str, **figures: Any) -> dict[str, Any]:
    """A screen row of ``ticker`` at the figures above, ``figures`` over them."""
    return {"ticker": ticker, "name": f"{ticker} Co"} | FIGURES | figures


def _cells(marked: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The cells ScreenTable draws for the one row ``marked``, by column, its bar off."""
    tree = node("Fairband.ScreenTable", [{"rows": [marked], "chooser": False}])
    tds = [e for e in elements(tree) if e.get("type") == "td"]
    assert len(tds) == len(DEFAULT_COLUMNS)
    return dict(zip(DEFAULT_COLUMNS, tds, strict=True))


def _tinted(marked: dict[str, Any]) -> list[str]:
    """The columns whose cell carries ``is-changed``, in the table's order."""
    return [
        key
        for key, cell in _cells(marked).items()
        if "is-changed" in str(cell["props"].get("className") or "").split()
    ]


def test_a_changed_price_is_marked_with_its_direction() -> None:
    got = node("marks", [[row("MGCO", price=47.1, priceToValue=1.18)], [row("MGCO")]])
    assert got["rows"][0]["changed"] == {"price": True, "priceToValue": True}
    assert (got["rows"][0]["priceMove"], got["prices"], got["values"]) == (-1, 1, 0)
    up = node("marks", [[row("MGCO", price=49.0, fairValue=41.0)], [row("MGCO")]])
    assert up["rows"][0]["changed"] == {"price": True, "fairValue": True}
    assert (up["rows"][0]["priceMove"], up["prices"], up["values"]) == (1, 1, 1)


def test_a_row_that_is_new_or_unchanged_carries_no_mark() -> None:
    """4.2: a row that is new, or gone, is not highlighted; one whose figures are all the same
    carries nothing. A key outside the figures (the name, the lists) is no change."""
    fresh = [row("MGCO", name="Renamed Co", watchlists=[1]), row("HGCO", price=12.0)]
    got = node("marks", [fresh, [row("MGCO"), row("MSCO", price=80.0)]])
    assert got["rows"] == fresh
    assert (got["prices"], got["values"]) == (0, 0)


def test_a_price_that_was_none_is_marked_with_no_direction() -> None:
    """A placeholder, a company with no snapshot yet, that gained one: its figures were none and
    are numbers now. Each is a change, and the price has no direction to show."""
    placeholder = {"ticker": "SUCO", "name": "SUCO Co"} | dict.fromkeys(FIGURES)
    got = node("marks", [[row("SUCO")], [placeholder]])
    [marked] = got["rows"]
    assert marked["changed"] == {key: True for key in FIGURES if key != "reviewed"}
    assert "priceMove" not in marked
    assert (got["prices"], got["values"]) == (1, 1)


def test_without_held_rows_nothing_is_marked() -> None:
    fresh = [row("MGCO"), row("MSCO", price=80.0)]
    got = node("marks", [fresh, None])
    assert got == {"rows": fresh, "prices": 0, "values": 0}


@pytest.mark.parametrize(
    ("changed", "tinted"),
    [
        ({"price": True, "designation": True}, ["price", "designation"]),
        ({"fairLow": True}, ["band"]),
        ({"fairHigh": True, "phase": True}, ["phase", "band"]),
        ({"mechanical": True, "reviewed": True, "priceToValue": True}, ["mechanical", "reviewed"]),
        (None, []),
    ],
)
def test_the_table_tints_only_the_changed_cells(
    changed: dict[str, bool] | None, tinted: list[str]
) -> None:
    """A changed figure's cell takes ``is-changed`` beside its own classes; the Fair band's cell
    reads the band's two ends; price ÷ value has no cell of its own."""
    marked = row("MGCO") | ({"changed": changed} if changed else {})
    assert _tinted(marked) == tinted
    price = _cells(marked)["price"]["props"]["className"].split()
    assert price[:2] == ["fb-num", "figure"]


@pytest.mark.parametrize(("move", "arrow"), [(1, "▲"), (-1, "▼"), (None, None)])
def test_a_changed_price_carries_its_arrow(move: int | None, arrow: str | None) -> None:
    """The direction before the price, no colour of its own, hidden from a screen reader; a price
    that changed with no direction (from none) has none."""
    marked = row("MGCO", changed={"price": True}) | ({"priceMove": move} if move else {})
    price = _cells(marked)["price"]
    moves = classed(price, "fb-screen__move")
    if arrow is None:
        assert moves == [] and text(price) == "$48.20"
        return
    [span] = moves
    assert (span["type"], span["props"]["aria-hidden"], text(span)) == ("span", "true", arrow)
    assert price["props"]["children"][0] == span
    assert text(price) == arrow + "$48.20"


def test_the_tint_fades_in_1_2_seconds_and_only_the_bar_stops_under_reduced_motion() -> None:
    """4.2 and 4.8: the tint is a grey from the border token, the arrow fades with it, and the run
    bar's fill eases; under the system's reduced-motion setting only the fill stops easing. The
    patch is marked with the spec's date and section."""
    css = _component_file("bundle.css")
    block = css[css.index("/* fairband: the end signal (spec 2026-11-23 refresh experience") :]
    for rule in (
        (
            "@keyframes fb-changed { from { background-color: color-mix(in srgb, var(--border) "
            "45%, transparent); } to { background-color: transparent; } }"
        ),
        "@keyframes fb-gone { from { opacity: 1; } to { opacity: 0; } }",
        ".is-changed { animation: fb-changed 1.2s ease-out; }",
        (
            ".fb-screen__move { color: var(--ink-muted); font-size: 10px; margin-right: 4px; "
            "animation: fb-gone 1.2s ease-out forwards; }"
        ),
        ".fb-run__seg { transition: width 200ms ease-out; }",
        "@media (prefers-reduced-motion: reduce) { .fb-run__seg { transition: none; } }",
    ):
        assert rule in block, rule
    assert re.findall(r"prefers-reduced-motion[^{]*\{([^}]*\})", block) == [
        " .fb-run__seg { transition: none; }"
    ]


def test_a_setting_the_reader_changed_does_not_flash() -> None:
    """The Methodology page marks a setting that differs from the default with the same class, in
    accent; that is no figure a run changed, so it takes no tint (4.8: three motions and no
    other)."""
    page = " ".join(_static_file("index.html").split())
    assert (
        ".app-prose .is-changed { color: var(--accent); text-decoration-color: var(--accent); "
        "animation: none; }"
    ) in page
