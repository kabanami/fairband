"""The Methodology view (spec 2026-11-04 7): the fragment's thirteen sections, its diagram, its live
spans and its examples; the script that fills the spans, wires the contents and the section hash
and maps a route to its section; the drawer's link to the row's route section; and the prose rule
of 7.1, every sentence of the fragment's prose at 25 words or fewer. The repository runs no
JavaScript tests, so the script is pinned by its content; the spans' names are checked against
the policy route itself."""

import re
from html import unescape

from fastapi.testclient import TestClient
from support.web import _static_file

from fairband.web.methodology_text import section_index, section_text

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
    "agents",
    "sources",
    "your-settings",
]
# The page's own panels: no id in the fragment may repeat one (controller ruling, task 10 review).
PANELS = {"header", "controls", "screen", "groups", "watchlists", "methodology", "settings"}
# Idioms the review found, and their kin; spec 7.1 asks for plain words.
IDIOMS = [
    "asks a lot",
    "room for error",
    "falls short",
    "under pressure",
    "goes on",
    "go on",
    "go without",
    "asks for",
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


def test_no_fragment_id_repeats_a_panel_s() -> None:
    html = _static_file("methodology.html")
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    assert ids & PANELS == set()
    assert '<a href="#methodology/your-settings">Your settings</a>' in html


def test_the_page_says_what_the_method_does() -> None:
    """The review's findings: Fairband's High Growth has a margin below zero (method 3.5 rule 4b);
    the Decline example names rule 2's three conditions; the run-off's value weights the floored
    value (6a.7); Z″ reads the income statement too (6a.8); the classifier's checks are notes,
    the word the flags section uses; no idiom."""
    html = re.sub(r"\s+", " ", _static_file("methodology.html"))  # lines wrap in the file
    life = _section(html, "life-cycle")
    high = life[life.index(">High Growth</h3>") : life.index(">Mature Growth</h3>")]
    assert "operating margin is still below zero but rising" in high
    classifier = _section(html, "classifier")
    assert "warn" not in classifier.lower()
    assert "Notes that do not change the phase" in classifier
    decline = _section(html, "decline")
    example = decline[decline.index("Worked example: 3M") :]
    reading = example[example.index("</table>") :]
    for condition in ("decile 1", "Close to zero or negative", "$3.0 billion a year", "three of"):
        assert condition in reading, condition
    assert "weights the floored value and the forced-sale value" in decline
    assert "four ratios from the balance sheet and the income statement" in decline
    prose = " ".join(_sentences(html)).lower()
    for idiom in IDIOMS:
        assert idiom not in prose, idiom


def test_the_page_says_what_method_0_9_changed() -> None:
    """Spec 2026-11-06 12: the margin direction reads the top two and the bottom two deciles, and
    Stable points to no phase (method 3.4); an established company is never a Start-up, and five
    profitable years on file make a company established (3.5); the own sales-to-capital bound and
    the dollar ramp (5a.4, 5a.5); the Decline consensus past year 3, the fade to zero and the flat
    terminal, and the implied decline rate on that fade (6a.2, 6a.5, 6a.9)."""
    html = re.sub(r"\s+", " ", _static_file("methodology.html"))  # lines wrap in the file
    classifier = _section(html, "classifier")
    direction = classifier[classifier.index(">The margin and its direction</h3>") :]
    direction = direction[: direction.index("</p>")]
    for text in ("the top two deciles", "the bottom two", "A stable margin points to no phase"):
        assert text in direction, text
    rules = classifier[classifier.index(">The rules</h3>") : classifier.index("</ol>")]
    start_up = rules[: rules.index("</li>")]
    assert "established company" in start_up and "never" in start_up
    assert "five of the fiscal years on file" in rules
    notes = classifier[classifier.index(">Notes that do not change the phase</h3>") :]
    notes = notes[: notes.index("</ul>")]
    assert "Rising to Mature Growth, Declining to Decline" in notes
    assert "Stable to Mature Stable" not in notes and "not made a Start-up" in notes
    growth = _section(html, "growth")
    capital = growth[growth.index(">Reinvestment, tax and cash</h3>") :]
    assert "half the mature peers' median" in capital[: capital.index("</p>")]
    margin = growth[growth.index(">The margin and the peers</h3>") :]
    assert "in dollars" in margin[: margin.index("</p>")]
    decline = _section(html, "decline")
    runoff = decline[decline.index(">The run-off</h3>") : decline.index("</ol>")]
    for text in ("past year 3", "fades to zero", "flat"):
        assert text in runoff, text
    assert "keeps shrinking" not in runoff
    price = decline[decline.index(">What the price needs</h3>") :]
    assert "fades to zero" in price[: price.index("</p>")]
    flags = _section(html, "flags")
    trend = flags[flags.index(">path-on-trend</code>") :]
    assert "years 1 to 3" in trend[: trend.index("</li>")]


def test_the_examples_state_method_0_9_s_rules() -> None:
    """The examples, re-read from the 0.9 revalue (CLAUDE.md: a change of method version re-reads
    its examples' figures): Microsoft's Stable margin raises no note, since Stable points to no
    phase; 3M's run-off names the years the consensus gives and the fade to zero with a flat
    terminal; the implied decline rate is named where the page sets it beside the trend's; the
    growth section's notes name the dollar ramp's."""
    html = re.sub(r"\s+", " ", _static_file("methodology.html"))  # lines wrap in the file
    asof = html[html.index("Figures as of") :]
    asof = asof[: asof.index("</p>")]
    assert "method 0.9" in asof and 'datetime="2026-11-06"' in asof
    assert "method 0.8" not in html
    classifier = _section(html, "classifier")
    msft = classifier[classifier.index("Worked example: Microsoft") :]
    assert '<td class="body">Checks</td><td class="body fb-num">none</td>' in msft
    assert "A stable margin points to no phase, so the drawer adds no note." in msft
    assert "Margin direction disagrees" not in msft and "Stable points to Mature" not in msft
    decline = _section(html, "decline")
    mmm = decline[decline.index("Worked example: 3M") :]
    assert "Consensus growth, years 2 to 4" in mmm
    assert "Decline rate, fading to zero by year 10" in mmm and "from year 4" not in mmm
    reading = mmm[mmm.index("</table>") :]
    for text in (
        "so the consensus runs to year 4",
        "fades in a straight line to zero by year 10",
        "then holds flat",
    ):
        assert text in reading, text
    assert "as the trend does" not in reading
    price = decline[decline.index(">What the price needs</h3>") :]
    assert "Set the implied decline rate beside the decline rate the trend gives." in price
    growth = _section(html, "growth")
    notes = growth[growth.index(">Flags on this route</h3>") :]
    notes = notes[: notes.index("</p>")]
    assert "A loss larger than revenue, moved in dollars, gets a note." in notes


def test_the_agents_section_reads(client: TestClient) -> None:
    """Spec 2026-11-06 Tier 2, 19, as amended: the section "Agents and reviews", before the
    sources and in the contents, says in plain words what an override is and that the engine
    computes the reviewed value, the bridge, the secondary valuation at the hurdle rate (a live
    value), the mid-cycle basis after Mature Stable's own scaling, guidance, the sensitivity
    reading, the agent's stance, the report's footnotes and where the records are read; it shows no example figure until a real review
    exists. The text is served as the MCP methodology tool reads it."""
    html = _static_file("methodology.html")
    assert '<li><a href="#methodology/agents">Agents and reviews</a></li>' in html
    agents = _section(re.sub(r"\s+", " ", html), "agents")
    assert 'data-policy="required_return"' in agents
    assert "data-find" not in agents and "Worked example" not in agents
    assert ("agents", "Agents and reviews") in section_index()
    found = section_text("agents", client.get("/api/policy").json(), None)
    assert found is not None
    title, text = found
    assert title == "Agents and reviews"
    for words in (
        "override",
        "reviewed value",
        "mechanical value",
        "bridge",
        "secondary valuation",
        "mid-cycle",
        "guidance",
        "sensitivity",
        "stance",
        "footnote",
        "Inbox",
    ):
        assert words in text, words
    # the live values, at the policy's defaults
    assert "at the locked hurdle rate, 9.0%" in text
    assert "at most the locked terminal growth, 3.0%" in text
    assert "—" not in text and "  " not in text
    # the task review: Mature Stable's own scaling comes before the mid-cycle override (method 6.2,
    # 14.4), a consensus step is named in words, and a refresh drops what has lapsed (14.6)
    for words in (
        "Possible cycle peak",
        "after any such scaling",
        "the consensus growth of year 2 or 3 (a consensus step)",
        "A range takes the midpoint.",
        "best effort, never required",
        "drops a period-tied override",
        "once its guided year has passed",
        "a valuation review for each company on the list with no open item",
        # spec 11 and 13.3, plan 3: the secondary valuation is the fallback only, refused where
        # the route or the review values the company, and no second value weighs on the stance
        # there; a refused row with a valued review weighs the price against the review's levels
        (
            "Where neither the route nor the review values the company, the report carries a"
            " secondary valuation: the fallback."
        ),
        (
            "Where the route or the review values the company there is none: the engine refuses"
            " the call, so no second value weighs on the stance."
        ),
        (
            "The agent weighs the price against the reviewed value's levels; on a refused row with"
            " none, the secondary valuation's."
        ),
        (
            "Where neither the route nor the review values the company, it shows the value of a"
            " secondary valuation instead"
        ),
        # spec 18.1, plan 3: the row's levels follow the reviewed value
        (
            "The band, the buy and trim levels and the designation follow the reviewed value; the"
            " Mechanical column keeps the engine's value."
        ),
        # the meter draws the band; the drawer, not the meter, adds the stance and the summary
        "The drawer's meter draws that band; the drawer adds the stance and the report's summary.",
    ):
        assert words in text, words
    assert "values a peak as if it lasted" not in text
    assert "second view" not in text and "Every report carries a secondary" not in text
    assert "draws that band, with the stance" not in text


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
    for code in (
        "few-analysts",
        "margin-direction-disagrees",
        "return-floored",
        "ncav-floor",
        "margin-ramp-in-dollars",
        "revenue-gap",
    ):
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
