"""The company page's price chart (the company page's design, 8.4; Review Focus 3): the rows of a
range, the change over it and its words, the geometry of the two plots on one time axis, the ticks,
the tag, the crosshair and its box, and the Price block the Overview draws first in its right
column. company.js and company_chart.js run in node after the bundle and app.js
(``support.page``), and the tests read what the chart's functions return and the trees its
builders draw.

The series are made here: ``TEN``, ten rows over two months to Friday 13 Nov 2026, rising from
$272.95 to $356.27; ``FALLING``, four rows over three months, from $19.93 to $11.64; and
``SERIES``, six hundred weekdays to the same Friday, from Monday 29 Jul 2024."""

import math
import re
from datetime import date, timedelta
from itertools import pairwise
from typing import Any

import pytest
from support import page_answers as answers
from support.page import NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (STATIC / "company.js", STATIC / "company_chart.js")
WIDTH = 720  # the width the chart draws at before it measures one
RANGES = ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y"]

TEN: list[list[Any]] = [
    ["2026-09-14", 272.95, 5_100_000],
    ["2026-09-22", 280.10, 6_200_000],
    ["2026-09-30", 291.40, 5_800_000],
    ["2026-10-06", 300.00, 7_400_000],
    ["2026-10-14", 310.55, 6_900_000],
    ["2026-10-20", 305.20, 8_100_000],
    ["2026-10-27", 320.75, 7_700_000],
    ["2026-11-03", 335.10, 9_300_000],
    ["2026-11-10", 349.80, 8_800_000],
    ["2026-11-13", 356.27, 7_650_200],
]

FALLING: list[list[Any]] = [
    ["2026-08-14", 19.93, 1_200_000],
    ["2026-09-15", 16.40, 1_500_000],
    ["2026-10-15", 13.05, 1_700_000],
    ["2026-11-13", 11.64, 2_100_000],
]


def _weekdays(newest: date, count: int) -> list[str]:
    """The ``count`` weekdays to ``newest``, oldest first."""
    days: list[str] = []
    day = newest
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day.isoformat())
        day -= timedelta(days=1)
    return days[::-1]


SERIES: list[list[Any]] = [
    [day, round(150 + 40 * math.sin(i / 45) + i * 0.05, 2), 3_000_000 + (i % 13) * 210_000]
    for i, day in enumerate(_weekdays(date(2026, 11, 13), 600))
]


def _chart(helper: str, *args: Any) -> Any:
    """What ``companyChart.<helper>`` returns on ``args``, company.js and company_chart.js loaded
    after app.js."""
    return node("companyChart." + helper, list(args), *SCRIPTS)


def _block(prices: list[list[Any]], range_id: str = "1Y", at: int | None = None) -> Any:
    """The Price block of ``prices`` at ``range_id``, the day ``at`` picked, at the width drawn
    before one is measured, with no handlers (none is called while it is drawn)."""
    return _chart("block", prices, range_id, at, WIDTH, None)


def _points(path: str) -> list[tuple[str, str, str]]:
    """Each command of an SVG path of moves and lines: its letter, its x and its y as written."""
    return re.findall(r"([ML])(-?[\d.]+) (-?[\d.]+)", path)


def _typed(tree: Any, kind: str) -> list[dict[str, Any]]:
    return [e for e in elements(tree) if e.get("type") == kind]


def _finite(value: Any) -> bool:
    return isinstance(value, int | float) and math.isfinite(value)


# ------------------------------------------------------------------------------------ the ranges


def test_each_range_keeps_the_rows_from_its_first_day() -> None:
    """A range runs from the day that many months before the newest row's day, that day kept
    where it is a row; year to date from the last day of the year before the newest row's. A
    first day that is not a row starts the range at the next row."""
    for range_id, first in (
        ("1M", "2026-10-13"),
        ("3M", "2026-08-13"),
        ("6M", "2026-05-13"),
        ("YTD", "2025-12-31"),
        ("1Y", "2025-11-13"),
    ):
        rows = _chart("inRange", SERIES, range_id)
        assert rows[0][0] == first, range_id
        assert rows == [row for row in SERIES if row[0] >= first], range_id
    assert [row[0] for row in _chart("inRange", TEN, "1M")] == [
        "2026-10-14",
        "2026-10-20",
        "2026-10-27",
        "2026-11-03",
        "2026-11-10",
        "2026-11-13",
    ]


def test_a_range_longer_than_the_series_keeps_every_row() -> None:
    """A company listed two months ago, and one listed under three years ago: every range the
    series does not fill keeps every row it has, and draws them."""
    for range_id in ("3M", "6M", "YTD", "1Y", "3Y", "5Y"):
        assert _chart("inRange", TEN, range_id) == TEN, range_id
    for range_id in ("3Y", "5Y"):
        assert _chart("inRange", SERIES, range_id) == SERIES, range_id
    tree = _block(TEN, "5Y")
    assert len(_points(_typed(tree, "path")[0]["props"]["d"])) == 10
    assert _chart("inRange", [], "1Y") == []


def test_the_change_over_a_range() -> None:
    """The newest close less the range's first, and that over the first (14.3); none for one row,
    for no row and for a first close of 0."""
    found = _chart("change", TEN)
    assert found["amount"] == pytest.approx(83.32)
    assert found["ratio"] == pytest.approx(83.32 / 272.95)
    falling = _chart("change", FALLING)
    assert falling["amount"] == pytest.approx(-8.29)
    assert falling["ratio"] == pytest.approx(-8.29 / 19.93)
    assert _chart("change", TEN[-1:]) is None
    assert _chart("change", []) is None
    assert _chart("change", [["2026-11-12", 0, 100], ["2026-11-13", 2.5, 100]]) is None


# ------------------------------------------------------------------------------- the geometry


def test_the_path_starts_at_the_first_close_and_ends_at_the_last() -> None:
    """The line runs from the plot's left edge at the first close to its right edge at the newest,
    one point a row, evenly spaced by trading day; the end marker and the tag stand on the newest
    close. So for the default width, a measured one, and every range of the long series."""
    g = _chart("geometry", TEN, WIDTH)
    assert g["path"].startswith("M4.0 ")
    points = _points(g["path"])
    assert [letter for letter, _, _ in points] == ["M"] + ["L"] * 9
    assert g["left"] == 4
    assert g["lastX"] == g["left"] + g["plotWidth"] == WIDTH - 58
    assert points[-1][1] == "662.0"
    assert float(points[-1][2]) == pytest.approx(g["lastY"], abs=0.051)
    ys = [float(y) for _, _, y in points]
    assert ys[0] == max(ys)  # the first close is the lowest, drawn lowest
    assert ys[-1] == min(ys) == pytest.approx(g["lastY"], abs=0.051)
    xs = [float(x) for _, x, _ in points]
    gaps = {round(b - a, 1) for a, b in pairwise(xs)}
    assert len(gaps) <= 2  # even, within the path's rounding
    assert g["width"] == WIDTH and g["height"] == 376
    measured = _chart("geometry", TEN, 400)
    assert measured["width"] == 400
    assert measured["lastX"] == 400 - 58
    assert _chart("geometry", TEN, None)["width"] == WIDTH
    for range_id in RANGES:
        rows = _chart("inRange", SERIES, range_id)
        each = _chart("geometry", rows, WIDTH)
        assert each["path"].startswith("M4.0 "), range_id
        assert len(_points(each["path"])) == len(rows), range_id
        assert each["lastX"] == each["left"] + each["plotWidth"], range_id
        assert 0 < len(each["xTicks"]) <= 7, range_id


def test_a_flat_series_has_a_finite_geometry() -> None:
    """A halted company, the same close every day, and a company with one row: the scale is
    widened by a step, so the line, the marker, the grid and the ticks are finite numbers and
    the path holds no NaN or Infinity."""
    flat = [[day, 180.0, volume] for day, _, volume in TEN]
    for rows in (flat, flat[-1:], [["2026-11-13", 0, 0]]):
        g = _chart("geometry", rows, WIDTH)
        assert "NaN" not in g["path"] and "Infinity" not in g["path"]
        assert len(_points(g["path"])) == len(rows)
        numbers = [g["lastX"], g["lastY"], *g["grid"], *g["xs"]]
        numbers += [tick["y"] for tick in g["yTicks"]] + [tick["x"] for tick in g["xTicks"]]
        numbers += [bar[key] for bar in g["bars"] for key in ("x", "y", "width", "height")]
        assert all(_finite(number) for number in numbers), rows
        assert g["yTicks"], rows
        assert all("NaN" not in tick["text"] for tick in g["yTicks"])
    g = _chart("geometry", flat, WIDTH)
    assert [tick["text"] for tick in g["yTicks"]] == ["179.5", "180.5"]
    one = _chart("geometry", flat[-1:], WIDTH)
    assert one["lastX"] == 4 + one["plotWidth"] / 2
    assert one["xTicks"] == []
    assert _chart("lead", flat[-1:], "1Y") is None


def test_an_empty_series_draws_its_sentence() -> None:
    """Review Focus 2 and 3: a company with no stored history, as the read of one with a profile
    and nothing else gives it. Every range draws No prices on file. in the plot's place, with no
    svg, no lead and the range buttons still there."""
    prices = answers.profile_only_overview()["prices"]
    assert prices == []
    assert _chart("geometry", prices, WIDTH) is None
    for range_id in RANGES:
        tree = _block(prices, range_id)
        [note] = classed(tree, "app-note")
        assert text(note) == "No prices on file."
        assert _typed(tree, "svg") == []
        assert classed(tree, "app-price__lead") == []
        assert [text(button) for button in classed(tree, "app-price__range")] == RANGES
    chart = _chart("Chart", {"prices": []})
    assert text(classed(chart, "app-note")[0]) == "No prices on file."
    assert _typed(chart, "svg") == []


def test_rows_without_a_close_or_a_volume_are_left_out_of_what_they_cannot_draw() -> None:
    """A row with no close is out of the line but keeps its day on the axis and its bar; one with
    no volume draws no bar; a range with no volume at all draws no bar and no greatest volume, and
    one with no close at all draws its sentence. Nothing divides by a missing figure."""
    rows = [list(row) for row in TEN]
    rows[4][1] = None
    rows[6][2] = None
    g = _chart("geometry", rows, WIDTH)
    assert len(_points(g["path"])) == 9
    assert g["lastX"] == g["left"] + g["plotWidth"]
    assert g["ys"][4] is None and len(g["xs"]) == 10
    assert [bar["i"] for bar in g["bars"]] == [0, 1, 2, 3, 4, 5, 7, 8, 9]
    assert _chart("change", rows)["amount"] == pytest.approx(83.32)
    no_volume = [[day, close, None] for day, close, _ in TEN]
    bare = _chart("geometry", no_volume, WIDTH)
    assert bare["bars"] == [] and bare["volumeMax"] is None
    tree = _block(no_volume)
    assert classed(tree, "app-price__volume") == []
    assert len(_typed(tree, "svg")) == 1
    tree = _block(rows, "1Y", 4)
    assert [text(line) for line in _typed(classed(tree, "app-price__tip")[0], "p")] == [
        "14 Oct 2026",
        "Close—",
        "Volume6.9M",
    ]
    assert classed(tree, "app-price__dot") == []
    assert len(classed(tree, "app-price__crosshair")) == 1
    unpriced = [[day, None, volume] for day, _, volume in TEN]
    assert _chart("geometry", unpriced, WIDTH) is None
    assert text(classed(_block(unpriced), "app-note")[0]) == "No prices on file."


# ---------------------------------------------------------------------------------- the ticks


def test_the_ticks_name_the_year_on_the_first_and_on_each_january() -> None:
    """An x tick stands at the first trading day of a month; the first shown names its year and so
    does each January, the others their month alone. At most seven: the past year's twelve
    months are thinned to every other one, counted from January, which stays."""
    rows = [row for row in SERIES if "2025-10-01" <= row[0] <= "2026-03-31"]
    ticks = _chart("xTicks", rows, False)
    assert [tick["text"] for tick in ticks] == ["Nov 2025", "Dec", "Jan 2026", "Feb", "Mar"]
    assert [rows[tick["i"]][0] for tick in ticks] == [
        "2025-11-03",
        "2025-12-01",
        "2026-01-01",
        "2026-02-02",
        "2026-03-02",
    ]
    year = _chart("inRange", SERIES, "1Y")
    ticks = _chart("xTicks", year, False)
    assert [tick["text"] for tick in ticks] == ["Jan 2026", "Mar", "May", "Jul", "Sep", "Nov"]
    assert len(ticks) <= 7
    six = _chart("xTicks", _chart("inRange", SERIES, "6M"), False)
    assert [tick["text"] for tick in six] == ["Jun 2026", "Jul", "Aug", "Sep", "Oct", "Nov"]
    g = _chart("geometry", TEN, WIDTH)
    assert [tick["text"] for tick in g["xTicks"]] == ["Oct 2026", "Nov"]
    assert [tick["x"] for tick in g["xTicks"]] == [g["xs"][3], g["xs"][7]]


def test_a_range_over_two_years_ticks_by_year() -> None:
    """Three and five years over a series of two years and more tick at each year's first trading
    day, the year alone; a range of two years or less ticks by month."""
    for range_id in ("3Y", "5Y"):
        g = _chart("geometry", _chart("inRange", SERIES, range_id), WIDTH)
        assert [tick["text"] for tick in g["xTicks"]] == ["2025", "2026"], range_id
        assert [SERIES[tick["i"]][0] for tick in g["xTicks"]] == ["2025-01-01", "2026-01-01"]
    two = [row for row in SERIES if row[0] >= "2024-11-13"]
    months = _chart("geometry", two, WIDTH)["xTicks"]
    assert months[0]["text"] == "Jan 2025"
    assert all(not tick["text"].isdigit() for tick in months)
    assert len(months) <= 7
    assert [tick["text"] for tick in _chart("xTicks", SERIES, True)] == ["2025", "2026"]


def test_the_y_tick_under_the_tag_is_left_out() -> None:
    """The close's scale runs over clean steps, a grid line at each; the newest close stands in a
    filled tag on the axis, two decimals and no $, and the tick it would cover, 350 under
    356.27, has no figure, while its grid line stays."""
    g = _chart("geometry", TEN, WIDTH)
    assert len(g["grid"]) == 4
    assert [tick["text"] for tick in g["yTicks"]] == ["250", "300", "400"]
    assert g["tag"]["text"] == "356.27"
    tree = _block(TEN)
    figures = [text(tick) for tick in classed(tree, "app-price__tick")]
    assert figures == ["250", "300", "400", "9.3M"]
    [tag] = classed(tree, "app-price__tag")
    assert text(tag) == "356.27"
    [box] = classed(tree, "app-price__tagbox")
    assert box["props"]["fill"] == "var(--accent)"
    assert box["props"]["y"] == pytest.approx(g["lastY"] - 9)


def test_the_lead_carries_the_sign_the_percent_and_the_range_s_words() -> None:
    """Above the plot the newest close in figure-lg, then the change over the range with its
    sign, its percent and the range in words, in the text's own colour; none for one row."""
    assert _chart("lead", TEN, "1Y") == "+$83.32 (+30.5%) past year"
    assert _chart("lead", FALLING, "3M") == "−$8.29 (−41.6%) past 3 months"
    assert _chart("lead", TEN[-1:], "1M") is None
    assert _chart("lead", [], "1M") is None
    tree = _block(TEN)
    [lead] = classed(tree, "app-price__lead")
    close, move = lead["props"]["children"]
    assert close["props"]["className"] == "figure-lg"
    assert text(close) == "$356.27"
    assert move["props"]["className"] == "figure app-price__move"
    assert text(move) == "+$83.32 (+30.5%) past year"
    falling = classed(_block(FALLING, "3M"), "app-price__move")[0]
    assert falling["props"]["className"] == "figure app-price__move"
    [one] = classed(_block(TEN[-1:]), "app-price__lead")
    assert [text(part) for part in one["props"]["children"] if part] == ["$356.27"]


# ------------------------------------------------------------------------------- the block


def test_the_chart_opens_at_the_past_year_with_its_ranges_in_the_head() -> None:
    """The Price block: its seven ranges, buttons in a group in its head, 1Y pressed when the
    chart opens; the lead, then the plot at the width drawn before one is measured. No table
    and no other button."""
    tree = _chart("Chart", {"prices": SERIES})
    assert tree["type"] == "section"
    [title] = _typed(tree, "h2")
    assert text(title) == "Price"
    [group] = classed(tree, "app-price__ranges")
    assert group["props"]["role"] == "group"
    buttons = classed(group, "app-price__range")
    assert [text(button) for button in buttons] == RANGES
    assert [button["props"]["aria-pressed"] for button in buttons] == [
        "false",
        "false",
        "false",
        "false",
        "true",
        "false",
        "false",
    ]
    assert {button["props"]["type"] for button in buttons} == {"button"}
    assert len(_typed(tree, "button")) == 7
    assert _typed(tree, "table") == []
    head = _typed(tree, "header")[0]
    assert group in list(elements(head))
    assert text(classed(tree, "app-price__move")[0]).endswith(" past year")
    [svg] = _typed(tree, "svg")
    assert svg["props"]["viewBox"] == "0 0 720 376"
    pressed = _block(SERIES, "YTD")
    assert [b["props"]["aria-pressed"] for b in classed(pressed, "app-price__range")][3] == "true"
    assert text(classed(pressed, "app-price__move")[0]).endswith(" year to date")


def test_the_marks_follow_the_design_system() -> None:
    """The close a 2px line in chart-1 with round joins and caps; the end marker 9px across in
    chart-1 with a 2px ring in surface-raised; the volume as bars in chart-context, none wider
    than chart-bar-max; grid lines solid in chart-grid; the two plots named, the volume's
    greatest labelled compact."""
    tree = _block(TEN)
    [line] = classed(tree, "app-price__line")
    assert line["type"] == "path"
    assert (line["props"]["stroke"], line["props"]["strokeWidth"]) == ("var(--chart-1)", 2)
    assert line["props"]["strokeLinejoin"] == line["props"]["strokeLinecap"] == "round"
    assert line["props"]["fill"] == "none"
    [end] = classed(tree, "app-price__end")
    g = _chart("geometry", TEN, WIDTH)
    assert (end["props"]["cx"], end["props"]["cy"]) == (g["lastX"], g["lastY"])
    assert end["props"]["r"] * 2 >= 8
    assert end["props"]["fill"] == "var(--chart-1)"
    assert (end["props"]["stroke"], end["props"]["strokeWidth"]) == ("var(--surface-raised)", 2)
    bars = classed(tree, "app-price__bar")
    assert len(bars) == 10
    assert {bar["props"]["fill"] for bar in bars} == {"var(--chart-context)"}
    assert max(bar["props"]["width"] for bar in bars) <= 24
    grid = classed(tree, "app-price__grid")
    assert len(grid) == 5  # four on the close's scale, the volume's baseline
    assert {line["props"]["stroke"] for line in grid} == {"var(--chart-grid)"}
    assert all("strokeDasharray" not in e["props"] for e in elements(tree))
    assert [text(name) for name in classed(tree, "app-price__name")] == ["Close, USD", "Volume"]
    [volume] = classed(tree, "app-price__volume")
    assert text(volume) == "9.3M"
    labels = [e for e in _typed(tree, "text") if "app-price__tag" not in e["props"]["className"]]
    assert len(labels) == 2 + 3 + 1 + 2  # the names, the close's ticks, the volume's, the days
    for label in labels:
        assert "fill" not in label["props"]  # text never wears the series colour


def test_the_hover_draws_a_crosshair_a_ringed_dot_and_a_box() -> None:
    """A day picked: a line across both plots at its x, a dot ringed in surface-raised on its
    close, its bar at full strength, and a box with its day, its close and its volume, on the
    plot's side with room. No day picked, none of them."""
    g = _chart("geometry", TEN, WIDTH)
    tree = _block(TEN, "1Y", 3)
    [cross] = classed(tree, "app-price__crosshair")
    assert cross["props"]["x1"] == cross["props"]["x2"] == g["xs"][3]
    assert cross["props"]["y1"] == g["top"]
    assert cross["props"]["y2"] == g["volumeTop"] + g["volumeHeight"]
    [dot] = classed(tree, "app-price__dot")
    assert (dot["props"]["cx"], dot["props"]["cy"]) == (g["xs"][3], g["ys"][3])
    assert dot["props"]["stroke"] == "var(--surface-raised)"
    [tip] = classed(tree, "app-price__tip")
    assert [text(line) for line in _typed(tip, "p")] == [
        "6 Oct 2026",
        "Close$300.00",
        "Volume7.4M",
    ]
    assert [text(name) for name in classed(tip, "app-price__tipname")] == ["Close", "Volume"]
    assert set(tip["props"]["style"]) == {"left"}  # the day is in the plot's left half
    opacity = [bar["props"]["opacity"] for bar in classed(tree, "app-price__bar")]
    assert opacity[3] == 1 and set(opacity[:3] + opacity[4:]) == {0.55}
    late = classed(_block(TEN, "1Y", 8), "app-price__tip")[0]
    assert set(late["props"]["style"]) == {"right"}
    none = _block(TEN)
    for name in ("app-price__crosshair", "app-price__dot", "app-price__tip"):
        assert classed(none, name) == []
    # a day the range no longer holds draws nothing
    assert classed(_block(TEN, "1M", 9), "app-price__tip") == []


def test_the_keys_move_the_crosshair_a_day_at_a_time() -> None:
    """The plot takes focus; there the arrow keys move the crosshair a day at a time, from the
    newest where none is picked, Home and End go to the ends, Escape clears it, and another key
    leaves it. The pointer picks the day nearest it; leaving the plot or its focus clears it."""
    for at, key, found in (
        (None, "ArrowLeft", 9),
        (None, "ArrowRight", 9),
        (5, "ArrowLeft", 4),
        (0, "ArrowLeft", 0),
        (5, "ArrowRight", 6),
        (9, "ArrowRight", 9),
        (5, "Home", 0),
        (5, "End", 9),
        (5, "Escape", None),
        (5, "a", 5),
    ):
        assert _chart("keyed", at, key, 10) == found, (at, key)
    g = _chart("geometry", TEN, WIDTH)
    for x, found in ((4, 0), (-40, 0), (662, 9), (900, 9), (g["xs"][3] + 30, 3), (300, 4)):
        assert _chart("nearest", g, x) == found, x
    [plot] = classed(_block(TEN), "app-price__plot")
    assert plot["props"]["tabIndex"] == 0
    assert plot["props"]["role"] == "group"
    assert plot["props"]["aria-label"] == "Price, past year"
    script = _static_file("company_chart.js")
    start = script.index("  function plot(")
    body = script[start : script.index("\n  }\n", start)]
    for handler in ("onKeyDown", "onBlur", "onMouseMove", "onMouseLeave", "preventDefault"):
        assert handler in body, handler


def test_the_script_and_the_chart_s_css() -> None:
    """The chart's script loads after the Overview's, whose function draws it; its CSS sets the
    ticks monospaced in ink-faint, the plots' names in the sans, the tag's figure in on-accent,
    the pressed range on accent-quiet, the box above the plot; nothing in it moves."""
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert scripts.index("company_chart.js") == scripts.index("company_overview.js") + 1
    rules = re.findall(r"\n  (\.app-price[^{]*)\{([^}]*)\}", html)
    css = {selector.strip(): " ".join(body.split()) for selector, body in rules}
    assert "font-family: var(--font-mono);" in css[".app-price__plot text"]
    assert "fill: var(--ink-faint);" in css[".app-price__plot text"]
    assert "font-family: var(--font-sans);" in css[".app-price__plot .app-price__name"]
    assert "fill: var(--on-accent);" in css[".app-price__plot .app-price__tag"]
    assert "background: var(--accent-quiet);" in css['.app-price__range[aria-pressed="true"]']
    assert "position: absolute;" in css[".app-price__tip"]
    assert "pointer-events: none;" in css[".app-price__tip"]
    assert "outline: 2px solid var(--focus-ring);" in css[".app-price__plot:focus-visible"]
    assert all("transition" not in body and "animation" not in body for body in css.values())
