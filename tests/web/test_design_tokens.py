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
    the rule of one series hue and before the polarity's; the section gives that chart the four
    series tokens, `chart-1` to `chart-4`, and keeps every other chart to one hue; the rule of
    one series hue sends the reader there; and the rule against two scales on one plot stands."""
    charts = _member("docs/charts.md").decode("utf-8")
    heading = "\n## Several series the reader picks\n"
    assert charts.count(heading) == 1
    emphasis = charts.index("\n## Emphasis, not categorical colour\n")
    polarity = charts.index("\n## Polarity uses the status pair\n")
    assert emphasis < charts.index(heading) < polarity
    section = " ".join(charts.split(heading, 1)[1].split("\n## ", 1)[0].split())
    assert "takes `chart-1` to `chart-4`. Every other chart keeps one hue" in section
    assert "Never a fifth colour: the chart holds four lines." in section
    assert "Never two scales on one plot." in section
    assert (
        "no categorical palette to get wrong — and if one ever appears, the answer is small "
        "multiples, not more hues. One chart is the exception; see *Several series the reader "
        "picks*.\n" in charts
    )
    assert "Never two y-scales on one plot" in charts
    assert (
        "None is a `phase-*`, `caution` or `critical` value. `chart-3` is a yellow near "
        "`caution`: it is a mark in a plot, never a status." in section
    )
    # what the four were held to, and the two checks they were not
    assert (
        "and each is 3:1 or more on `surface-raised`, in both themes. They are not held to one "
        "lightness band or to the chroma floor: `chart-1` is the accent, which is lighter than the "
        "band in the dark theme and under the chroma floor in the light one, and the others differ "
        "in lightness, which is part of what keeps each pair apart. None is a `phase-*`" in section
    )
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
