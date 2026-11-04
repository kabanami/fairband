"""The Methodology view (spec 2026-11-04 7): the fragment's twelve sections, its diagram, its live
spans and its examples; the script that fills the spans, wires the contents and the section hash
and maps a route to its section; the drawer's link to the row's route section; and the prose rule
of 7.1, every sentence of the fragment's prose at 25 words or fewer. The repository runs no
JavaScript tests, so the script is pinned by its content; the spans' names are checked against
the policy route itself."""

import re
from html import unescape

from fastapi.testclient import TestClient
from support.web import _static_file

SECTIONS = [
    "what",
    "life-cycle",
    "classifier",
    "value",
    "mature-growth",
    "mature-stable",
    "growth",
    "decline",
    "start-up",
    "flags",
    "sources",
    "settings",
]
PHASES = ["Start-up", "Young Growth", "High Growth", "Mature Growth", "Mature Stable", "Decline"]
EXAMPLES = ("MSFT", "KO", "CRWD", "ROKU", "MMM", "RVMD")
# The eleven quality warnings that count in the Flags column (spec 9.5).
QUALITY_WARNINGS = [
    "large-nri",
    "value-spread",
    "margin-flag",
    "z-distress",
    "f-score-low",
    "reinvesting-in-decline",
    "equity-raise",
    "negative-fcf",
    "heavy-capex",
    "burn-cover-short",
    "consensus-recovery",
]
MOAT_OR_INDEX = re.compile(r"\.(None|Narrow|Wide|\d+)$")
MOST_WORDS = 25


def _section(html: str, section: str) -> str:
    return html.split(f'<section id="{section}"')[1].split("</section>")[0]


def test_fragment_sections_diagram_and_examples() -> None:
    html = _static_file("methodology.html")
    for section in SECTIONS:
        assert f'<section id="{section}"' in html
    # the sections in the order of spec 7.2
    assert [html.index(f'<section id="{s}"') for s in SECTIONS] == sorted(
        html.index(f'<section id="{s}"') for s in SECTIONS
    )
    assert "<svg" in html and 'role="img"' in html and "<title" in html and "<desc" in html
    assert html.count("var(--phase-") >= 6 and "url(" not in html and "<img" not in html
    assert "Figures as of" in html
    for symbol in EXAMPLES:
        assert f'data-find="{symbol}"' in html


def test_diagram_draws_six_bands_two_curves_and_the_counts() -> None:
    """Spec 7.3: a 960 by 320 viewBox, one band per phase on the phase ramp at low opacity, the
    revenue curve in the series hue and the earnings curve in muted ink over a zero line, each
    phase's name in caption and its live count in figure-sm under it; every colour a token."""
    html = _static_file("methodology.html")
    svg = html[html.index("<svg") : html.index("</svg>")]
    assert 'viewBox="0 0 960 320"' in svg and 'aria-labelledby="' in svg
    for n in range(1, 7):
        assert f'fill="var(--phase-{n})" fill-opacity="0.18"' in svg
    assert svg.count("<rect") == 6
    assert 'stroke="var(--chart-1)"' in svg and 'stroke="var(--ink-muted)"' in svg
    assert 'stroke="var(--chart-grid)"' in svg
    for phase in PHASES:
        assert re.search(rf'<text class="caption" [^>]*y="300"[^>]*>{phase}</text>', svg), phase
        assert re.search(rf'<text data-count="{phase}" class="figure-sm" [^>]*y="316"', svg), phase
    assert re.findall(r'(?:fill|stroke)="(#[0-9a-fA-F]+|rgb[^"]*)"', svg) == []
    assert "<animate" not in svg and "<style" not in svg


def test_every_data_policy_name_is_served(client: TestClient) -> None:
    """Every span the page fills names a value GET /api/policy serves, a moat key or an index
    after the name; the counts name the six phases, the unclassified and the universe."""
    html = _static_file("methodology.html")
    cited = re.findall(r'data-policy="([^"]+)"', html)
    names = {MOAT_OR_INDEX.sub("", c) for c in cited}
    served = client.get("/api/policy").json()["values"]
    assert names and names <= set(served), names - set(served)
    for c in cited:  # a moat key on a by-moat value, an index on a pair or a list
        key = MOAT_OR_INDEX.search(c)
        if key and key.group(1) in ("None", "Narrow", "Wide"):
            assert isinstance(served[MOAT_OR_INDEX.sub("", c)]["value"], dict), c
        elif key:
            assert isinstance(served[MOAT_OR_INDEX.sub("", c)]["value"], list), c
    counts = set(re.findall(r'data-count="([^"]+)"', html))
    assert counts == {*PHASES, "unclassified", "universe"}
    deciles = {int(n) for n in re.findall(r'data-decile="(\d+)"', html)}
    assert deciles and deciles <= set(range(1, 10))
    # every live span starts as an em dash, which the script replaces
    for span in re.findall(r"<span data-(?:policy|count|decile)=\"[^\"]+\">([^<]*)</span>", html):
        assert span == "—"


def test_sources_have_links() -> None:
    html = _static_file("methodology.html")
    sources = _section(html, "sources")
    assert sources.count('href="https://') >= 8
    assert "Base Rate Book" in sources and "pages.stern.nyu.edu" in sources
    for work in ("Dickinson", "Altman", "Piotroski", "Measuring the Moat", "McKinsey", "Graham"):
        assert work in sources, work
    assert "OECD" in sources and "docs/method.md" in sources


def test_flags_section_lists_the_quality_warnings_then_the_notes() -> None:
    """Spec 7.2 item 10: the eleven warnings that count, then the notes; each code once, in a
    code chip, and nowhere else in the page's prose."""
    html = _static_file("methodology.html")
    flags = _section(html, "flags")
    warnings, notes = flags.split('id="flags-notes"')
    chips = re.findall(r'<code class="fb-tag figure-sm">([^<]+)</code>', flags)
    assert len(chips) == len(set(chips))  # each code once
    assert re.findall(r'<code class="fb-tag figure-sm">([^<]+)</code>', warnings) == (
        QUALITY_WARNINGS
    )
    for code in ("few-analysts", "margin-direction-disagrees", "return-floored", "ncav-floor"):
        assert f'<code class="fb-tag figure-sm">{code}</code>' in notes, code
    outside = html.replace(flags, "")
    assert "<code" not in outside


def test_examples_open_today_s_row() -> None:
    html = _static_file("methodology.html")
    for symbol in EXAMPLES:
        assert f'<a href="#" data-find="{symbol}">Open today\'s row</a>' in html
    assert html.count('<table class="fb-table') >= 6


def _sentences(html: str) -> list[str]:
    """The sentences of the fragment's paragraphs and list items, tags stripped, the tables and
    the code chips left out."""
    text = re.sub(r"<table\b.*?</table>", " ", html, flags=re.DOTALL)
    text = re.sub(r"<svg\b.*?</svg>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<code\b.*?</code>", " ", text, flags=re.DOTALL)
    blocks = re.findall(r"<(p|li)\b[^>]*>(.*?)</\1>", text, flags=re.DOTALL)
    sentences = []
    for _, block in blocks:
        plain = unescape(re.sub(r"<[^>]+>", "", block))
        plain = re.sub(r"\s+", " ", plain).strip()
        sentences += [s for s in re.split(r"(?<=[.!?])\s+", plain) if s]
    return sentences


def test_prose_sentences_are_short() -> None:
    """Spec 7.1: one idea a sentence, 25 words or fewer."""
    sentences = _sentences(_static_file("methodology.html"))
    assert len(sentences) > 100
    long = [f"{len(s.split())} words: {s}" for s in sentences if len(s.split()) > MOST_WORDS]
    assert long == [], "\n".join(long)


def test_drawer_links_to_the_route_section() -> None:
    js = _static_file("app.js")
    assert "'How Fairband values a ' + " in js and "'#methodology/' + P.methodologySection(" in js
    link = js[js.index("function methodologyLink(") :]
    link = link[: link.index("\n  }\n")]
    assert "if (!r.route || !phase) return null;" in link
    assert "methodologyLink(r, phase)" in js


def test_methodology_js_fills_the_spans_and_maps_the_routes() -> None:
    js = _static_file("methodology.js")
    assert "P.onShow.methodology = " in js
    assert "fetch('/static/methodology.html')" in js and "panel.innerHTML = " in js
    for route in ("/api/policy", "/api/deciles", "/api/groups?by=phase", "/api/screen"):
        assert f"P.getJson('{route}" in js, route
    assert (
        "var SECTIONS = {\n    'mature-growth': 'mature-growth', 'mature-stable': 'mature-stable',\n"
        "    'revenue-growth': 'growth', 'decline': 'decline', 'start-up': 'start-up'\n  };"
    ) in js
    assert "P.methodologySection = function (route) {" in js
    formats = js[js.index("var FORMATS = {") : js.index("\n  };\n", js.index("var FORMATS = {"))]
    for unit in ("fraction", "points", "years", "days", "times", "usd", "count", "exchanges"):
        assert f"\n    {unit}: " in formats, unit
    assert "P.find(" in js and "[data-find]" in js
    assert "[data-policy]" in js and "[data-count]" in js and "[data-decile]" in js
    assert "scrollIntoView" in js and "P.section" in js


def test_page_loads_the_script_and_the_prose_styles(client: TestClient) -> None:
    page = _static_file("index.html")
    assert '<script src="/static/methodology.js"></script>' in page
    assert page.index("/static/settings.js") < page.index("/static/methodology.js")
    assert ".app-prose {" in page and "max-width: 70ch;" in page
    assert client.get("/static/methodology.html").status_code == 200


def test_the_methodology_panel_never_fades() -> None:
    """Its example tables are figures as of a named date, not the running refresh's."""
    js = _static_file("controls.js")
    assert "if (id !== 'methodology') panels[id].classList.toggle(RECOMPUTING, alive);" in js
