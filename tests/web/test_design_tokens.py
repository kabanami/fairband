"""The design system's three more series colours and its rule for the chart that takes them (the
Financials tab's design, 7.6 and 10): ``chart-2``, ``chart-3`` and ``chart-4`` stand after
``chart-1`` in ``tokens.json`` and in both themes of ``tokens.css``; the vendored copy the app
serves equals the archive's, byte for byte; the archive's ``charts.md`` names the chart with
several series and keeps its rule against two scales on one plot; and the brand book and
``SpreadChart.md`` make room for that one chart. The archive is read in place, never unpacked
(CLAUDE.md)."""

import json
import re
import tarfile
from pathlib import Path

from support.page import STATIC

ARCHIVE = (
    Path(__file__).parent.parent.parent
    / "docs"
    / "design-system"
    / "fairband-design-system_4.tar.gz"
)
ROOT = "fairband-design-system"
VENDORED = STATIC / "design-system" / "tokens"

# Each new token, its dark value and its light value (spec 7.6).
SERIES = {
    "chart-2": ("#437dde", "#1b3d9c"),
    "chart-3": ("#f3c530", "#b5820c"),
    "chart-4": ("#c05296", "#c562b2"),
}
USAGES = {
    "chart-2": (
        "The second series hue, blue, on a chart whose lines the reader picks. Never on a chart "
        "with a subject."
    ),
    "chart-3": (
        "The third series hue, yellow, on a chart whose lines the reader picks. A mark in a plot, "
        "never a status: `caution` is the status."
    ),
    "chart-4": "The fourth and last series hue, magenta, on a chart whose lines the reader picks.",
}
EXCEPTION = (
    "One chart has no subject, the Financials tab's, whose lines the reader picks: there "
    "`chart-1` to `chart-4` name the lines."
)
# charts.md's section for that chart, whole, from its heading to the line before the next.
SECTION = """
## Several series the reader picks

One chart in Fairband has no subject: the Financials tab's, where the reader picks up to four
lines and none is the point more than another. That chart, and only a chart like it, takes
`chart-1` to `chart-4`. Every other chart keeps one hue and `chart-context`.

- A line takes the lowest of the four that is free when it is picked and keeps it until it
  leaves the chart. Taking one line off never repaints the others. One line alone wears
  `chart-1`.
- Never a fifth colour: the chart holds four lines.
- Lines of one unit share a plot and a scale. Another unit takes a plot of its own under it, on
  the same periods. Never two scales on one plot.
- An amount, a per-share figure or a share count is a column from zero; a rate is a line on an
  axis that fits its range.
- With one line, a figure below zero takes `chart-neg-3`, the polarity pair. With several, a
  column wears its line's colour above zero and below: colour is identity there.
- The legend is the row of labels above the plot, each a swatch, a name and the newest figure.
  Text never wears a series colour.
- This chart spans the page, so a column is at most 44px wide alone and 28px among several.
  `chart-bar-max` stays `HistoryBars`'s.
- The four were measured as a set: every pair is 10.6 or more apart under simulated protan and
  deutan sight and 21 or more under full sight (OKLab ΔE × 100), and each is 3:1 or more on
  `surface-raised`, in both themes. They are not held to the palette method's lightness band
  (OKLCH L 0.48 to 0.67 in the dark theme, 0.43 to 0.77 in the light one) or to its chroma floor
  (0.10). `chart-1` is the accent, which is lighter than the band in the dark theme and under
  the floor in the light one; `chart-3` is lighter than the band in the dark theme and `chart-2`
  darker than it in the light one. Two pairs share a lightness, `chart-2` and `chart-4` in the
  dark theme and `chart-3` and `chart-4` in the light one: hue alone keeps them apart. Under
  simulated tritan sight, which the method reports and does not gate, the light theme's
  `chart-3` and `chart-4` are 4.7 apart: the hover box names each line with its figure, and a
  period's columns stand in the labels' order. None is a `phase-*`, `caution` or `critical`
  value. `chart-3` is a yellow near `caution`: it is a mark in a plot, never a status.
"""


def _member(name: str) -> bytes:
    """A file of the archive, by its path under the root folder, read without unpacking."""
    with tarfile.open(ARCHIVE, "r:gz") as archive:
        member = archive.extractfile(f"{ROOT}/{name}")
        assert member is not None, name
        return member.read()


def test_the_three_series_tokens_stand_in_both_themes() -> None:
    """In the vendored tokens.css each of --chart-2, --chart-3 and --chart-4 is declared three
    times: its dark value once, in the dark root, and its light value twice, in the light theme
    and the light preference. In tokens.json the three follow chart-1 in order, each with its two
    values and its usage, and chart-1's usage names the exception."""
    css = (VENDORED / "tokens.css").read_text(encoding="utf-8")
    light = css.index('[data-theme="light"] {')
    for token, (dark_value, light_value) in SERIES.items():
        declared = re.findall(rf"^\s*--{token}: (\S+);$", css, re.MULTILINE)
        assert declared == [dark_value, light_value, light_value], token
        assert css.index(f"  --{token}: {dark_value};") < light, token
    colours = json.loads((VENDORED / "tokens.json").read_text(encoding="utf-8"))["color"]
    names = [entry["name"] for entry in colours["tokens"]]
    first = names.index("chart-1")
    assert names[first : first + 5] == ["chart-1", "chart-2", "chart-3", "chart-4", "chart-context"]
    entries = {entry["name"]: entry for entry in colours["tokens"]}
    for token, (dark_value, light_value) in SERIES.items():
        assert entries[token]["value"] == {"dark": dark_value, "light": light_value}, token
        assert entries[token]["usage"] == USAGES[token], token
    assert entries["chart-1"]["usage"].endswith(" " + EXCEPTION)


def test_the_vendored_tokens_are_the_archive_s() -> None:
    """tokens.json and tokens.css under static/design-system/tokens equal the archive's, byte for
    byte."""
    for name in ("tokens.json", "tokens.css"):
        assert (VENDORED / name).read_bytes() == _member(f"tokens/{name}"), name


def test_the_chart_rules_name_the_chart_with_several_series() -> None:
    """The archive's charts.md has the section for the chart whose lines the reader picks, after
    the rule of one series hue and before the polarity's, and the section is SECTION, word for
    word; the rule of one series hue sends the reader there, the paragraph on the categorical
    checks sends the reader there too, and the rule against two scales on one plot stands."""
    charts = _member("docs/charts.md").decode("utf-8")
    heading = "\n## Several series the reader picks\n"
    assert charts.count(heading) == 1
    emphasis = charts.index("\n## Emphasis, not categorical colour\n")
    polarity = charts.index("\n## Polarity uses the status pair\n")
    assert emphasis < charts.index(heading) < polarity
    start = charts.index(heading) + 1  # the heading's own line
    section = charts[start : charts.index("\n## ", start)]
    assert " ".join(section.split()) == " ".join(SECTION.split())
    assert (
        "no categorical palette to get wrong — and if one ever appears, the answer is small "
        "multiples, not more hues. One chart is the exception; see *Several series the reader "
        "picks*.\n" in charts
    )
    assert "Never two y-scales on one plot" in charts
    assert (
        "\nNo other chart has a categorical palette, so the six categorical checks do not apply to "
        "them; *Several series the reader picks* says what its four colours were held to. "
        "`chart-context` is held to the 3:1 mark-contrast floor" in charts
    )
    assert "Because there is no categorical palette" not in charts
    assert "apply to that one chart alone" not in charts


def test_the_rest_of_the_design_system_allows_the_one_chart() -> None:
    """The brand book's paragraph on charts and SpreadChart's rule against a third line, which
    said Fairband has one series hue and no categorical palette, make room for the chart whose
    lines the reader picks."""
    book = _member("docs/brand-book.md").decode("utf-8")
    assert (
        "plus a validated diverging scale for anything measured against a baseline; the one chart "
        "whose lines the reader picks takes four series hues." in book
    )
    spread = _member("docs/components/SpreadChart.md").decode("utf-8")
    assert "and Fairband has no categorical palette for a chart with a subject.\n" in spread
    assert "no categorical palette by design" not in spread
