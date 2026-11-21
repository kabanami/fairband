"""The Methodology view (spec 2026-11-04 7): the fragment's fourteen sections, its diagram, its live
spans and its examples; the script that fills the spans and wires the contents and the section
hash; and the prose rule of 7.1, every sentence of the fragment's prose at 25 words or fewer.
The repository runs no JavaScript tests, so the script is pinned by its content; the spans'
names are checked against the policy route itself."""

import re
from html import unescape

from fastapi.testclient import TestClient
from support.web import _static_file

from fairband.engine.flags import QUALITY_WARNINGS as ENGINE_WARNINGS
from fairband.refresh.rates import NO_RATE
from fairband.web.methodology_text import section_index, section_text

SECTIONS = [
    "what",
    "life-cycle",
    "classifier",
    "value",
    "foreign-filers",
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
# The twelve quality warnings, which count (spec 9.5; spec 2026-11-13 8) and mark a mechanical value
# from the policy's count (spec 2026-11-19 7.5), the warning one-time-items where large-nri stood,
# first (spec 2026-11-19 7.2).
QUALITY_WARNINGS = [
    "one-time-items",
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
    "share-count-gap",
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


def test_the_examples_are_dated_to_method_1_4() -> None:
    """The examples, re-read under method 1.4 (CLAUDE.md: a change of method version re-reads its
    examples' figures), are dated to that run: the data of 11 Nov 2026, the quarterly balance
    sheets of 14 Nov, the closes of 13 Nov and Roku's of 6 Nov. The four that read the balance
    sheet name its period, and the two with a minority interest show it (spec 2026-11-13 12.2,
    13). They keep the rules 0.9 brought: Microsoft's Stable margin raises no note, since Stable
    points to no phase; 3M's run-off names the years the consensus gives and the fade to zero with
    a flat terminal; the implied decline rate is named where the page sets it beside the trend's;
    the growth section's notes name the dollar ramp's. Re-read on 15 Nov 2026, they stand unchanged
    under method 1.5: none has a revenue step the thin rule leaves out. Re-read on 19 Nov 2026, they
    stand unchanged under method 1.6: none is an ADR or holds a vendor's ratio (spec 2026-11-19
    6.2)."""
    html = re.sub(r"\s+", " ", _static_file("methodology.html"))  # lines wrap in the file
    asof = html[html.index("Figures as of") :]
    asof = asof[: asof.index("</p>")]
    assert "method 1.4" in asof
    for day in ("2026-11-11", "2026-11-14", "2026-11-13", "2026-11-06"):
        assert f'datetime="{day}"' in asof, day
    assert "Roku's is the close of" in asof
    assert "method 0.8" not in html and "method 0.9" not in asof and "method 1.0" not in asof
    assert "14 Nov 2026</time> and are unchanged under methods 1.5 and 1.6." in asof
    assert "methods 1.1, 1.2 and 1.3" not in asof
    # the balance sheet's period under each table that reads it, the minority interest where it is
    # above zero (CrowdStrike, 3M) and none where it is nil (Roku, Revolution Medicines)
    growth = _section(html, "growth")
    roku = growth[growth.index("Worked example: Roku") :]
    crwd = growth[growth.index("Worked example: CrowdStrike") :].replace(roku, "")
    decline = _section(html, "decline")
    mmm = decline[decline.index("Worked example: 3M") :]
    rvmd = _section(html, "start-up")
    rvmd = rvmd[rvmd.index("Worked example: Revolution Medicines") :]
    for example, period in (
        (crwd, "fiscal 2027 Q2"),
        (roku, "fiscal 2026 Q3"),
        (mmm, "fiscal 2026 Q3"),
        (rvmd, "fiscal 2026 Q3"),
    ):
        assert f'<p class="caption">Balance sheet of {period}.</p>' in example, period
    assert '<td class="body">Less minority interest</td>' in crwd and "$38 million" in crwd
    assert '<td class="body">Minority interest</td>' in mmm and "$1.0 billion" in mmm
    assert "minority interest" not in roku.lower() and "minority interest" not in rvmd.lower()
    floor = '<td class="body">Net current asset value less minority interest, a share</td>'
    assert floor in mmm and '<td class="body">Net current asset value a share</td>' not in mmm
    for text in (
        "where 3M's earlier sheets showed about $50 million",
        "The engine takes the vendor's line as it stands.",
        "corrects it with the override balance.minority",
    ):
        assert text in mmm, text
    classifier = _section(html, "classifier")
    msft = classifier[classifier.index("Worked example: Microsoft") :]
    assert '<td class="body">Checks</td><td class="body fb-num">none</td>' in msft
    assert "A stable margin points to no phase, so no note is added." in msft
    assert "Margin direction disagrees" not in msft and "Stable points to Mature" not in msft
    assert "1.3 points a year · decile 7 · Stable" in msft
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


def test_the_page_says_what_method_1_0_changed() -> None:
    """Spec 2026-11-09 12: the charge pays for revenue growth, a year can pay out less than nothing
    when growth outruns the return, and the return holds through the growth above the belief, then
    fades to the terminal return; the two mature routes' lists say the same, and their examples
    show it in the figures of the run the page is dated to, under method 1.4."""
    html = re.sub(r"\s+", " ", _static_file("methodology.html"))  # lines wrap in the file
    value = _section(html, "value")
    charge = value[value.index(">The reinvestment charge</h3>") : value.index(">The moat and")]
    for text in (
        "next year's revenue growth over the return on new capital",
        "Earnings that grow faster than revenue come from wider margins",
        "pays out less than nothing: the owners put money in to fund the growth",
        "holds while growth stays above the belief",
        "fades in equal steps to the terminal return by the end of the runway",
    ):
        assert text in charge, text
    growth = _section(html, "mature-growth")
    steps = growth[growth.index(">The steps</h3>") : growth.index("</ol>")]
    assert "next year's revenue growth" in steps and "then fades to the terminal return" in steps
    assert "pays out less than nothing" in growth and "pays out nothing" not in growth
    msft = growth[growth.index("Worked example: Microsoft") :]
    for figure in ("20.6%, 22.5%", "$497", "1.05 · Near", "6.2%", "through year 6"):
        assert figure in msft, figure
    assert "$516" not in msft and "6.4%" not in msft and "$498" not in msft
    stable = _section(html, "mature-stable")
    assert "fades in equal steps from year 1" in stable
    ko = stable[stable.index("Worked example: Coca-Cola") :]
    for figure in ("$61", "$49", "2.03 · Well above", "11.7%", "fading in equal steps to 13.0%"):
        assert figure in ko, figure
    assert "$63" not in ko and "10.4%" not in ko and "11.3%" not in ko
    flags = _section(html, "flags")
    above = flags[flags.index(">growth-above-return</code>") :]
    assert "pays out less than nothing" in above[: above.index("</li>")]


def test_a_thin_revenue_year_takes_the_earnings_growth() -> None:
    """Spec 2026-11-14 6.2, method 1.5, as narrowed on 2026-11-15: the Mature Growth steps say that
    a year whose consensus revenue growth is above the policy's size and rests on fewer than the
    policy's analysts, or no count, takes the earnings growth."""
    html = re.sub(r"\s+", " ", _static_file("methodology.html"))  # lines wrap in the file
    growth = _section(html, "mature-growth")
    steps = growth[growth.index(">The steps</h3>") : growth.index("</ol>")]
    assert (
        "A year's consensus revenue growth above "
        '<span data-policy="thin_revenue_step_max">—</span> is left out when fewer than '
        '<span data-policy="analyst_min">—</span> analysts forecast it, or the count is missing. '
        "That year then takes the consensus earnings growth."
    ) in steps


def test_the_equity_steps_take_the_minority_interest_off() -> None:
    """Spec 2026-11-13 13: the growth, Decline and Start-up entries take the minority interest off
    the owners' claim beside debt, and the page says it is taken at book, where a market value
    would be the better figure."""
    html = re.sub(r"\s+", " ", _static_file("methodology.html"))  # lines wrap in the file
    growth = _section(html, "growth")
    cash = growth[growth.index(">Reinvestment, tax and cash</h3>") :]
    cash = cash[: cash.index("<h3")]
    for text in (
        "Cash is added, and debt and the minority interest are taken off.",
        "the share of the company's subsidiaries that outside owners hold",
        "at its book value on the balance sheet, though a market value would be the better figure",
    ):
        assert text in cash, text
    assert "Cash is added, debt is taken off" not in growth
    decline = _section(html, "decline")
    runoff = decline[decline.index(">The run-off</h3>") : decline.index("</ol>")]
    assert "plus cash on hand, less debt and the minority interest, is the going-concern" in runoff
    floor = decline[decline.index(">The floor and distress</h3>") :]
    floor = floor[: floor.index("<h3")]
    assert "(current assets less all liabilities), less the minority interest, a share" in floor
    assert "The owners get that plus cash, less debt and the minority interest." in floor
    # the floored value names the floor, never the bare net current asset value
    assert "or the liquidation floor where it replaces that value" in floor
    assert "or the net current asset value, whichever the floor gives" not in floor
    flags = _section(html, "flags")
    ncav = flags[flags.index(">ncav-floor</code>") :]
    assert (
        "The net current asset value, less the minority interest, is above the run-off's value "
        "and sets the floor." in ncav[: ncav.index("</li>")]
    )
    net_cash = flags[flags.index(">below-net-cash</code>") :]
    assert (
        "A Start-up's market value is at or below its cash less debt and the minority interest."
        in net_cash[: net_cash.index("</li>")]
    )
    start = _section(html, "start-up")
    for text in (
        "The price here is the market value plus debt and the minority interest, less cash.",
        "The cash floor (cash less debt and the minority interest, a share)",
    ):
        assert text in start, text


def test_the_foreign_filers_section_reads(client: TestClient) -> None:
    """Spec 2026-11-10 10: a section on foreign filers after the value's, in the contents, in the
    page's register: the reporting currency, the rate, the inflation differential with one worked
    example, the share basis and the bound, the two bounds live from the policy; the refusals'
    words. The refusals list names the currency's refusals in place of the foreign filer's, and the
    rate note names the stale-rate bound. No code chip outside the flags section."""
    html = _static_file("methodology.html")
    assert '<li><a href="#methodology/foreign-filers">Foreign filers</a></li>' in html
    flat = re.sub(r"\s+", " ", html)
    section = _section(flat, "foreign-filers")
    for span in ('data-policy="inflation_max"', 'data-policy="fx_stale_days"'):
        assert span in section, span
    assert "data-find" not in section and "<code" not in section
    assert ("foreign-filers", "Foreign filers") in section_index()
    found = section_text("foreign-filers", client.get("/api/policy").json(), None)
    assert found is not None
    title, text = found
    assert title == "Foreign filers"
    for words in (
        "reporting currency",
        "the currency of its newest annual income statement",
        "units of the currency one US dollar buys",
        "divided by the rate on the price's day",
        "inflation differential",
        "1.0404 ÷ 1.02 − 1 = 2.0%",
        "1.09 × 1.02 − 1 = 11.18%",
        "per ADS",
        "older than 7 days",
        "above 10.0%",
        # the five rates the method restates (method 7.5; fix round 1; the cap of method 1.2), the
        # inflation addition in the page's own words, as the Mature Growth section names it
        "The hurdle rate, terminal growth, the inflation the belief adds and the growth caps",
        "So is the cap on a return measured without goodwill.",
        "restates each of the five by the inflation differential",
        # the refusals quoted as the server words them, one each (fix round 1)
        "“reporting currency unknown”",
        f"“{NO_RATE.format(code='<code>')}”",
        "“no inflation projection for <code>”",
        "“<code>: expected inflation <π>% above the 10% bound”",
        "“share basis unclear: ...”",
    ):
        assert words in text, words
    assert "—" not in text and "  " not in text
    value = _section(flat, "value")
    refusals = value[value.index(">Refusals</h3>") :]
    assert "A foreign filer:" not in refusals
    # the share basis's refusal in one wording wherever the page names it (fix round 1)
    basis = "a depositary receipt's newest share count matches the quote's on no basis"
    assert basis in refusals and basis in section and "matches the price's" not in flat
    assert (
        "A currency the method cannot price: unknown, with no exchange rate or inflation"
        " projection, or with inflation above the bound."
    ) in refusals
    flags = _section(flat, "flags")
    stale = flags[flags.index(">fx-stale</code>") :]
    assert 'older than <span data-policy="fx_stale_days">—</span>' in stale[: stale.index("</li>")]
    sources = _section(flat, "sources")
    assert 'id="src-imf"' in sources and 'id="src-ias29"' in sources


def test_the_page_names_the_half_year_window() -> None:
    """Spec 2026-11-10 8 (plan 2): the Mature Growth steps say year 1 covers the next four
    quarters, or two half-years for a company that reports twice a year, and the
    ``trailing-on-fiscal-year`` note names both."""
    flat = re.sub(r"\s+", " ", _static_file("methodology.html"))
    mature = _section(flat, "mature-growth")
    steps = mature[mature.index(">The steps</h3>") :]
    covers = "It covers the next four quarters (two half-years for a company that reports twice a"
    assert covers in steps[: steps.index("</ol>")]
    flags = _section(flat, "flags")
    note = flags[flags.index(">trailing-on-fiscal-year</code>") :]
    names = "The last four quarters, or two half-years, do not follow each other"
    assert names in note[: note.index("</li>")]


def test_the_page_states_the_anchor_on_a_thin_window() -> None:
    """Spec 2026-11-13 9a, as amended: the Mature Growth steps say a quarter or half-year with too
    few analysts in the last fiscal year year 1 reaches takes that year's level from its yearly
    consensus, year 1 keeping its quarters' estimates plus its share of the gap, where the year's
    consensus has enough analysts and each of its quarters an estimate; a year under way is never
    corrected. The route's flags and the ``thin-ntm`` entry say the note shows where nothing
    corrects a thin period, and why."""
    flat = re.sub(r"\s+", " ", _static_file("methodology.html"))
    mature = _section(flat, "mature-growth")
    steps = mature[mature.index(">The steps</h3>") :]
    steps = steps[: steps.index("</ol>")]
    analysts = '<span data-policy="analyst_min">—</span>'
    for words in (
        f"A quarter or half-year may have fewer than {analysts} analysts",
        "When it falls in the last fiscal year that year 1 reaches",
        "the consensus for that whole year sets the year's level",
        "plus its share of the gap between that year's consensus and the sum of the year's",
        f"This needs {analysts} analysts or more on the year's consensus",
        "A fiscal year already under way is never corrected",
    ):
        assert words in steps, words
    route_flags = mature[mature.index(">Flags on this route</h3>") :]
    assert "that the consensus for its fiscal year does not correct" in route_flags
    flags = _section(flat, "flags")
    thin = flags[flags.index(">thin-ntm</code>") :]
    thin = thin[: thin.index("</li>")]
    assert "The consensus for its fiscal year does not correct it" in thin
    assert "That year is already under way" in thin
    assert f"has fewer than {analysts} analysts, or one of its quarters has no estimate" in thin
    assert "cannot take their place" not in thin  # the first form's words


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
        # spec 2026-11-13 7.3: a nil stock pay may last, until the stored figures show stock pay
        (
            "For a company that pays no stock, a nil figure may last until a refresh finds stock"
            " pay in the company's figures."
        ),
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
        # the company page's design, 8.2 and 11: the drawer's meter draws the band; the company
        # page draws it too, with the report's stance and its link under it
        (
            "The drawer's meter draws that band. The company page, which the ticker opens, draws"
            " it too, and under it the latest report's stance and a link to the report."
        ),
        # spec 2026-11-14 7: a refresh scales an earlier override at a split, and says so
        (
            "After a stock split, an earlier override in dollars a share or in shares is scaled"
            " to the new shares, and the review says so."
        ),
        # spec 2026-11-14 8: an override the row's route no longer reads drops
        "When the company's phase moves, an override that only the old route read drops too.",
    ):
        assert words in text, words
    assert "values a peak as if it lasted" not in text
    assert "second view" not in text and "Every report carries a secondary" not in text
    assert "draws that band, with the stance" not in text
    # spec 2026-11-19 7.5: the Flags and the Warnings columns and the Clean filter have gone
    assert "Flags and Warnings columns" not in text and "Clean filter" not in text


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


def test_a_mechanical_value_keeps_one_time_items() -> None:
    """Spec 2026-11-19 7.1 and 7.5: the engine takes no non-recurring gap, so the value section
    says a mechanical value is preliminary and keeps one-time items, which a review takes out, in
    the Words table's sentences; Mature Stable's first step starts from trailing earnings, and
    neither that step nor Coca-Cola's example takes one-off items out."""
    html = re.sub(r"\s+", " ", _static_file("methodology.html"))  # lines wrap in the file
    value = _section(html, "value")
    assert (
        "A mechanical value is preliminary: fixed rules made it, and no one checked it. It "
        "includes one-time items. A review takes them out."
    ) in value
    stable = _section(html, "mature-stable")
    steps = stable[stable.index("<ol") : stable.index("</ol>")]
    first = steps[steps.index("<li>") : steps.index("</li>")]
    assert first == "<li>Trailing earnings are the starting point."
    assert "one-off" not in stable and "Normalized earnings (" not in stable
    assert "over the last twelve months. The engine grows that" in stable


def test_the_flags_section_names_the_mark_and_the_hover(client: TestClient) -> None:
    """Spec 2026-11-19 7.5: the screen draws no flag; a dot marks a mechanical value with the
    policy's count of quality warnings or more and no review, and a hover on the value names them;
    the notes are read by an agent and never count. The page names no Flags column, Warnings
    column or Clean filter, which have gone, and a flag's word is no longer the screen's. The
    count is the served policy's, as the MCP methodology tool reads it."""
    html = re.sub(r"\s+", " ", _static_file("methodology.html"))  # lines wrap in the file
    flags = _section(html, "flags")
    intro = flags[: flags.index("<h3")]
    for sentence in (
        (
            "Each has a short word and one sentence, which an agent reads when it researches the"
            " company."
        ),
        "The screen draws no flag.",
        (
            "A dot before a mechanical value marks one with"
            ' <span data-policy="warning_mark_min">—</span> quality warnings or more and no review.'
        ),
        "A hover on the value names its warnings and says the value is preliminary.",
        "Every other flag is a note: read by an agent, never counted.",
    ):
        assert sentence in intro, sentence
    notes = flags[flags.index('id="flags-notes"') :]
    assert "They are read by an agent and never count." in notes[: notes.index("</p>")]
    classifier = _section(html, "classifier")
    assert "An agent reads the notes, and a report's Appendix A lists them" in classifier
    for gone in ("Flags column", "Warnings column", "Clean filter", "a short word for the screen"):
        assert gone not in html, gone
    found = section_text("flags", client.get("/api/policy").json(), None)
    assert found is not None
    marks = (
        "A dot before a mechanical value marks one with 3 quality warnings or more and no review."
    )
    assert marks in found[1]


def test_flags_section_lists_the_quality_warnings_then_the_notes() -> None:
    """Spec 7.2 item 10: the twelve warnings that count, then the notes; each code once, in a
    code chip, and nowhere else in the page's prose. The count in words is the engine's, and the
    share-count warning names its band by the policy's two ends (spec 2026-11-13 8)."""
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
        "return-without-goodwill",
        "return-floored",
        "ncav-floor",
        "margin-ramp-in-dollars",
        "revenue-gap",
        "fx-stale",
        "stock-pay-missing",
        "sbc-basis-uncertain",
        "thin-ntm",
        "sheet-shift",
        "override-split-scaled",
    ):
        assert f'<code class="fb-tag figure-sm">{code}</code>' in notes, code
    # the review's split note follows the split's own (spec 2026-11-14 7)
    split = [c for c in chips if c in ("split-pending", "override-split-scaled", "basis-scaled")]
    assert split == ["split-pending", "override-split-scaled", "basis-scaled"]
    # the two stock-pay notes follow the basis note, and the thin NTM note follows the few
    # analysts note, in the route's order (method 5.11)
    order = [
        c for c in chips if c in ("sbc-basis-unknown", "stock-pay-missing", "sbc-basis-uncertain")
    ]
    assert order == ["sbc-basis-unknown", "stock-pay-missing", "sbc-basis-uncertain"]
    path = [c for c in chips if c in ("few-analysts", "thin-ntm", "step-series-disagree")]
    assert path == ["few-analysts", "thin-ntm", "step-series-disagree"]
    # the sheet-shift note follows the line flags, as the routes give it (method 5a.13)
    bridge = [c for c in chips if c in ("line-not-presented:…", "sheet-shift", "charge-zeroed")]
    assert bridge == ["line-not-presented:…", "sheet-shift", "charge-zeroed"]
    text = re.sub(r"\s+", " ", flags)
    assert "Twelve flags are quality warnings" in text and len(QUALITY_WARNINGS) == 12
    assert set(QUALITY_WARNINGS) == ENGINE_WARNINGS
    # the warning one-time-items, by its word and threshold, on Mature Stable alone; the two
    # codes method 1.7 removes are gone (spec 2026-11-19 7.2)
    one_time = text[text.index('<li><span class="label">One-time items</span>') :]
    one_time = one_time[: one_time.index("</li>")]
    assert '<span data-policy="one_time_items_share">—</span>' in one_time
    assert "Mature Stable" in one_time
    assert "large-nri" not in chips and "consensus-basis-unknown" not in chips
    assert "nri_flag_share" not in html
    gap = text[text.index(">share-count-gap</code>") :]
    gap = gap[: gap.index("</li>")]
    for span in ("share_count_gap_band.0", "share_count_gap_band.1"):
        assert f'<span data-policy="{span}">—</span>' in gap, span
    assert "a share class or units that convert to shares" in gap
    thin = text[text.index(">thin-ntm</code>") :]
    thin = thin[: thin.index("</li>")]
    assert '<span data-policy="analyst_min">—</span>' in thin and "guidance" in thin
    # the sheet-shift note names its multiple and is silent where an agent sets the figure
    shift = text[text.index(">sheet-shift</code>") :]
    shift = shift[: shift.index("</li>")]
    assert '<span data-policy="sheet_shift_multiple">—</span>' in shift
    assert "an agent sets that figure" in shift
    # each stock-pay note is silent under the agent's input that decides it and under a guided
    # NTM EPS (method 5.11)
    for code, setting in (
        ("stock-pay-missing", "an agent sets the stock pay"),
        ("sbc-basis-uncertain", "an agent sets the stock-pay basis"),
    ):
        note = text[text.index(f">{code}</code>") :]
        note = note[: note.index("</li>")]
        assert setting in note and "the next twelve months' EPS from guidance" in note, code
    outside = html.replace(flags, "")
    assert "<code" not in outside
    assert "currency-unknown" not in chips  # method 1.1 refuses an unknown currency instead


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


def test_methodology_js_fills_the_spans() -> None:
    js = _static_file("methodology.js")
    assert "P.onShow.methodology = " in js
    assert "fetch('/static/methodology.html')" in js and "panel.innerHTML = " in js
    for route in ("/api/policy", "/api/deciles", "/api/groups?by=phase", "/api/screen"):
        assert f"P.getJson('{route}" in js, route
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
