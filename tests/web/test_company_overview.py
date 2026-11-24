"""The company page's Overview tab (the company page's design, 8): at the left the Company block,
the Fairband value block and the Key statistics block; at the right the price chart
(``test_company_chart``), Price facts and News; the tab's function that draws them, the rule
that ends the two columns on one line, and the second read that brings newer news (10.5).
company.js, company_overview.js and company_chart.js run in node after the bundle and app.js
(``support.page``), and the tests read the trees their builders return; the second read's
functions run in node on their own, with a fetch and a state the test gives them.

The company is ``page_answers``' LFOX: valued at $196.50 against a price of $182.40, its levels
$147.38, $176.85 to $216.15 and $294.75; reporting in New Taiwan dollars, so its enterprise value,
its revenue and its dividend a share carry the code TWD; three stories on file, the third at an
address that is not a web address."""

import json
import re
import subprocess
from typing import Any

import pytest
from support import page_answers as answers
from support import page_payloads as payloads
from support.page import NODE, STATIC, classed, elements, node, text
from support.web import _static_file

from fairband.vendors import page_fmp

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (STATIC / "company.js", STATIC / "company_overview.js", STATIC / "company_chart.js")
COMPANY = answers.OVERVIEW["company"]
STATISTICS = answers.OVERVIEW["statistics"]


def _page(helper: str, *args: Any) -> Any:
    """What ``companyPage.<helper>`` returns on ``args``, company.js, company_overview.js and
    company_chart.js loaded after app.js, as the page loads them."""
    return node("companyPage." + helper, list(args), *SCRIPTS)


def _rule(selector: str) -> str:
    """The declarations of the page's one rule whose line opens with ``selector``, on one line."""
    css = _static_file("index.html")
    ends = [m.end() for m in re.finditer(r"(?m)^[ \t]*" + re.escape(selector), css)]
    assert len(ends) == 1, selector
    return " ".join(css[ends[0] : css.index("}", ends[0])].split())


def _lists(tree: Any) -> list[list[tuple[str, str]]]:
    """Each list of names and figures in ``tree``, as its rows' (name, figure) texts."""
    return [
        [
            (text(classed(row, "app-kv__k")[0]), text(classed(row, "app-kv__v")[0]))
            for row in classed(kv, "app-kv__row")
        ]
        for kv in classed(tree, "app-kv")
    ]


def _fact(tree: Any, name: str) -> dict[str, Any]:
    """The figure's element of the row named ``name``; there is one."""
    [found] = [
        classed(row, "app-kv__v")[0]
        for row in classed(tree, "app-kv__row")
        if text(classed(row, "app-kv__k")[0]) == name
    ]
    return found


def _links(tree: Any) -> list[dict[str, Any]]:
    return [e for e in elements(tree) if e.get("type") == "a"]


def _with(**groups: dict[str, Any]) -> dict[str, Any]:
    """The overview answer with the named statistics groups' fields replaced."""
    statistics = {
        name: (fields | groups[name]) if name in groups else fields
        for name, fields in STATISTICS.items()
    }
    return answers.OVERVIEW | {"statistics": statistics}


# ------------------------------------------------------------------------------- the company


def test_the_company_block() -> None:
    """The brief, clamped to three lines under Show more, then eight facts in two lists of four:
    the CEO, the website, the employees as a count and the day it listed; the sector, the
    industry, the country and the exchange."""
    company = COMPANY | {"employees": 167000, "listed": "1980-12-12"}
    tree = _page("Company", {"company": company})
    assert tree.get("type") == "section"
    [title] = [e for e in elements(tree) if e.get("type") == "h2"]
    assert text(title) == "Company"
    [brief] = classed(tree, "app-company__brief")
    assert brief["type"] == "p"
    assert text(brief) == COMPANY["brief"]
    assert brief["props"]["className"].split() == ["body", "app-company__brief", "is-clamped"]
    [more] = classed(tree, "app-company__more")
    assert (more["type"], more["props"]["type"]) == ("button", "button")
    assert text(more) == "Show more"
    assert more["props"]["aria-expanded"] == "false"
    [facts] = classed(tree, "app-company__two")
    assert _lists(facts) == [
        [
            ("CEO", "Mara Vellini"),
            ("Website", "lanternfield.example"),
            ("Employees", "167,000"),
            ("Listed", "12 Dec 1980"),
        ],
        [
            ("Sector", "Technology"),
            ("Industry", "Semiconductors"),
            ("Country", "TW"),
            ("Exchange", "NYSE"),
        ],
    ]
    found = list(elements(tree))
    assert found.index(brief) < found.index(more) < found.index(facts)
    # the figures in figure, the words in body
    assert "figure" in _fact(tree, "Employees")["props"]["className"].split()
    assert "figure" in _fact(tree, "Listed")["props"]["className"].split()
    assert "body" in _fact(tree, "CEO")["props"]["className"].split()


def test_a_text_value_wraps_inside_its_cell_and_a_figure_does_not() -> None:
    """A list's value in body, a word or a name, wraps inside its half of the row, so a long
    industry (``Drug Manufacturers - Specialty & Generic``) or a long name stays inside its list;
    a value in figure stays on one line (the decision log of 2026-11-17). Each of the Company
    block's facts is marked by its kind: the six words in body, the employees and the day it
    listed in figure."""
    assert _rule(".app-kv__v {") == "text-align: right; white-space: nowrap;"
    wraps = "white-space: normal; overflow-wrap: anywhere; min-width: 0;"
    assert _rule(".app-kv__v.body {") == wraps
    long = COMPANY | {
        "industry": "Drug Manufacturers - Specialty & Generic",
        "ceo": "Maria Alejandra Fernandez-Villanueva de la Cruz",
    }
    tree = _page("Company", {"company": long})
    kinds = {
        text(classed(row, "app-kv__k")[0]): classed(row, "app-kv__v")[0]["props"]["className"]
        for row in classed(tree, "app-kv__row")
    }
    words = ("CEO", "Website", "Sector", "Industry", "Country", "Exchange")
    assert kinds == {name: "body app-kv__v" for name in words} | {
        "Employees": "figure app-kv__v",
        "Listed": "figure app-kv__v",
    }
    assert text(_fact(tree, "Industry")) == "Drug Manufacturers - Specialty & Generic"


def test_the_brief_opens_and_closes() -> None:
    """Open, the brief is whole and the button says Show less; the component keeps whether it is
    open and turns it at a click."""
    tree = _page("companyBlock", COMPANY, True, None)
    [brief] = classed(tree, "app-company__brief")
    assert "is-clamped" not in brief["props"]["className"].split()
    [less] = classed(tree, "app-company__more")
    assert text(less) == "Show less"
    assert less["props"]["aria-expanded"] == "true"
    [closed] = classed(_page("companyBlock", COMPANY, False, None), "app-company__more")
    assert text(closed) == "Show more"
    script = _static_file("company_overview.js")
    start = script.index("  function Company(props) {")
    component = script[start : script.index("\n  }\n", start)]
    assert "React.useState(false)" in component
    clamp = _rule(".app-company__brief.is-clamped {")
    assert "-webkit-line-clamp: 3;" in clamp and "overflow: hidden;" in clamp


def test_the_company_block_is_keyed_on_the_company() -> None:
    """The Overview keys the Company block on the company, as it keys the chart, so a brief opened
    on one company's page is closed on the next one's."""
    for symbol in (answers.SYMBOL, "BRK.B"):
        tree = _page("draw.overview", answers.OVERVIEW | {"symbol": symbol}, answers.DETAIL)
        company = tree["props"]["children"][0]["props"]["children"][0]
        assert company["props"]["company"] == COMPANY
        assert company["props"]["key"] == "company " + symbol


def test_a_company_with_no_brief_draws_no_paragraph_and_no_button() -> None:
    for brief in (None, ""):
        tree = _page("Company", {"company": COMPANY | {"brief": brief}})
        assert classed(tree, "app-company__brief") == []
        assert classed(tree, "app-company__more") == []
        assert len(classed(tree, "app-kv__row")) == 8


def test_the_website_is_a_link_only_when_it_is_a_web_address() -> None:
    """A link opens in a new tab with no opener and no referrer, its text the address without its
    scheme and a leading www.; any other address is drawn as text, none as the dash (10.6)."""
    for address, shown in (
        ("https://www.acme.example", "acme.example"),
        ("http://acme.example/about", "acme.example/about"),
        ("HTTPS://WWW.ACME.EXAMPLE", "ACME.EXAMPLE"),
    ):
        value = _fact(_page("Company", {"company": COMPANY | {"website": address}}), "Website")
        [link] = _links(value)
        assert link["props"]["href"] == address
        assert text(link) == shown
        assert link["props"]["target"] == "_blank"
        assert link["props"]["rel"] == "noopener noreferrer"
    for address, shown in (
        ("javascript:alert(1)", "javascript:alert(1)"),
        ("data:text/html,<b>x</b>", "data:text/html,<b>x</b>"),
        ("www.acme.example", "www.acme.example"),
        ("", "—"),
        (None, "—"),
    ):
        value = _fact(_page("Company", {"company": COMPANY | {"website": address}}), "Website")
        assert _links(value) == []
        assert text(value) == shown


@pytest.mark.parametrize(
    ("address", "href"),
    [
        ("https://www.acme.example", "https://www.acme.example"),
        ("http://acme.example/a?b=1", "http://acme.example/a?b=1"),
        ("HTTPS://acme.example", "HTTPS://acme.example"),
        ("javascript:alert(1)", None),
        (" javascript:alert(1)", None),
        ("java\tscript:alert(1)", None),
        ("JavaScript:alert(1)", None),
        ("data:text/html,<script>alert(1)</script>", None),
        ("ftp://acme.example", None),
        ("www.acme.example", None),
        ("//acme.example", None),
        ("", None),
        (None, None),
        (42, None),
    ],
)
def test_safe_href_gives_only_a_web_address(address: Any, href: str | None) -> None:
    assert _page("safeHref", address) == href


# --------------------------------------------------------------------------- the Fairband value


def _chip(tree: Any) -> dict[str, Any]:
    """The bundle's BasisChip of a helper's tree, undrawn: its props as given."""
    [chip] = [e for e in elements(tree) if "basis" in e["props"]]
    return chip


def _meters(tree: Any) -> list[dict[str, Any]]:
    """The bundle's BandMeter elements of a helper's tree, undrawn: their props as given."""
    return [e for e in elements(tree) if "fairValue" in e["props"]]


def _marks(tree: Any) -> list[dict[str, Any]]:
    """The warnings marks the page hands the bundle, undrawn: the elements given ``words``."""
    return [e for e in elements(tree) if "words" in e["props"]]


# The open company's note and the hover of a value with three warnings, as the Words table gives
# them, and the warnings mark the page hands the bundle for them, undrawn.
OPEN_NOTE = (
    "Preliminary estimate only. To ask an agent for a reviewed valuation, click Request research."
)
THREE = ["heavy capital spending", "negative free cash flow", "new shares issued"]
HOVER = (
    "3 warnings: heavy capital spending; negative free cash flow; new shares issued. " + OPEN_NOTE
)
MARK: dict[str, Any] = {"props": {"words": THREE, "children": []}}


def test_the_value_block_valued() -> None:
    """The basis chip, mechanical, in the block's head; the meter as the drawer draws it, its price
    in figure; the four levels in the screen's words, in two columns; no report's line."""
    tree = _page("value", answers.DETAIL)
    assert tree.get("type") == "section"
    [head] = [e for e in elements(tree) if e.get("type") == "header"]
    [title] = [e for e in elements(head) if e.get("type") == "h2"]
    assert text(title) == "Fairband value"
    assert _chip(head)["props"] == {"basis": "mechanical", "children": []}
    [meter] = _meters(tree)
    assert meter == node("meter", [answers.DETAIL, False])
    [levels] = classed(tree, "app-company__two")
    assert _lists(levels) == [
        [("Fair value", "$196.50"), ("Buy level", "$147.38")],
        [("Fair band", "$176.85 – $216.15"), ("Trim level", "$294.75")],
    ]
    found = list(elements(tree))
    assert found.index(meter) < found.index(levels)
    assert classed(tree, "app-company__research") == []
    assert classed(tree, "fb-stance") == []
    assert classed(tree, "app-refusal") == []
    assert "Open the report" not in text(tree)


def test_the_value_block_reviewed_and_with_a_report() -> None:
    """The review counts: the chip says reviewed and the meter and the levels are the review's.
    The published report's line stands under a rule: the stance chip in the Stance column's
    classes, the mode and the day, the principal chip, and the link to the report on the company
    page's Research tab, the address ``researchHref`` gives."""
    detail = answers.reviewed_detail()
    detail["report"] |= {"createdAt": "2026-11-11T12:00:00+00:00"}
    tree = _page("value", detail)
    assert _chip(tree)["props"]["basis"] == "reviewed"
    [meter] = _meters(tree)
    assert meter == node("meter", [detail, False])
    assert meter["props"]["fairValue"] == 182.0
    [levels] = classed(tree, "app-company__two")
    assert _lists(levels) == [
        [("Fair value", "$182.00"), ("Buy level", "$145.60")],
        [("Fair band", "$163.80 – $200.20"), ("Trim level", "$273.00")],
    ]
    [line] = classed(tree, "app-company__research")
    [stance] = classed(line, "fb-stance")
    assert stance.get("type") == "span"
    assert stance["props"]["className"] == "fb-stance fb-stance--hold label"
    assert stance["props"].get("title") is None
    assert text(stance) == "hold"
    [when] = [e for e in elements(line) if e.get("type") == "p"]
    assert text(when) == "full report, 11 Nov 2026"
    [chip] = [e for e in elements(line) if "principal" in e["props"]]
    assert (chip["props"]["principal"], chip["props"]["actor"]) == ("agent", "claude-opus-5-5")
    [link] = _links(line)
    # the company page's Research tab on the latest report (the Research tab's design, 7.1)
    assert link["props"]["href"] == "#company/LFOX/research" == node("researchHref", ["LFOX"])
    assert text(link) == "Open the report"
    found = list(elements(line))
    assert found.index(stance) < found.index(when) < found.index(chip) < found.index(link)
    assert "border-top: 1px solid var(--hairline);" in _rule(".app-company__research {")


def test_the_report_s_line_of_an_expired_report_and_a_symbol_to_encode() -> None:
    detail = answers.reviewed_detail()
    detail["report"] |= {"expired": True, "stance": "trim", "mode": "valuation review"}
    detail["result"] |= {"symbol": "A&B"}
    tree = _page("value", detail)
    [stance] = classed(tree, "fb-stance")
    assert stance["props"]["className"] == "fb-stance fb-stance--trim fb-stance--expired label"
    assert stance["props"]["title"] == "The snapshot window of this report has expired"
    [line] = classed(tree, "app-company__research")
    [when] = [e for e in elements(line) if e.get("type") == "p"]
    assert text(when).startswith("valuation review, ")
    [link] = _links(line)
    assert link["props"]["href"] == "#company/A%26B/research" == node("researchHref", ["A&B"])


def test_the_value_block_adds_one_line_for_a_value_expired_early() -> None:
    """Spec 2026-11-23 held reviewed value, 5.7: the Overview adds nothing for a reviewed value
    that is current, and one line under the levels, before the report's line, for one that
    expired early: the drawer's line (``FairbandPage.heldPart``)."""
    held = {
        "state": "expired-early",
        "earlyAt": "2026-11-14",
        "reasons": ["The company has reported a newer period (to 26 Dec 2026)."],
        "reading": None,
        "readingRefusal": None,
        "readingLine": None,
        "validUntil": "2027-02-01",
    }
    current = answers.reviewed_detail()
    current["review"] = current["review"] | {"held": held | {"state": "current", "reasons": []}}
    assert classed(_page("value", current), "app-held") == []
    early = answers.reviewed_detail()
    early["review"] = early["review"] | {"held": held}
    tree = _page("value", early)
    [line] = classed(tree, "app-held")
    words = [text(e) for e in elements(line) if e.get("type") == "button"]
    assert words == ["× Expired early 14 Nov 2026 · 1 reason ▸"]
    order = [e for e in elements(tree) if e.get("type") is not None]
    [levels] = classed(tree, "app-company__two")
    assert order.index(levels) < order.index(line)


def test_the_value_block_of_a_refused_row() -> None:
    """A refused row with no band shows its refusal's sentence in the meter's place, and no
    levels; its chip stays mechanical, the engine's."""
    tree = _page("value", answers.refused_detail())
    [refusal] = classed(tree, "app-refusal")
    assert refusal["type"] == "p"
    assert text(refusal) == answers.REFUSAL
    assert _meters(tree) == []
    assert classed(tree, "app-company__two") == []
    assert classed(tree, "app-kv") == []
    assert "Fair value" not in text(tree)
    assert _chip(tree)["props"]["basis"] == "mechanical"


def test_a_refused_row_with_a_review_or_a_secondary_band_draws_that_band() -> None:
    """A refused row whose review has a value draws the review's band and levels, as the meter
    does; one whose secondary valuation counts, the secondary's. Either is reviewed, and the
    refusal is not drawn in the band's place."""
    reviewed = answers.refused_detail() | {"review": answers.REVIEW}
    tree = _page("value", reviewed)
    assert _meters(tree) == [node("meter", [reviewed, False])]
    assert _lists(classed(tree, "app-company__two")[0])[0] == [
        ("Fair value", "$182.00"),
        ("Buy level", "$145.60"),
    ]
    assert _chip(tree)["props"]["basis"] == "reviewed"
    assert classed(tree, "app-refusal") == []

    secondary = answers.refused_detail() | {"secondary": SECONDARY}
    tree = _page("value", secondary)
    assert _meters(tree) == [node("meter", [secondary, False])]
    assert _lists(classed(tree, "app-company__two")[0]) == [
        [("Fair value", "$150.00"), ("Buy level", "$112.50")],
        [("Fair band", "$135.00 – $165.00"), ("Trim level", "$225.00")],
    ]
    assert _chip(tree)["props"]["basis"] == "reviewed"


SECONDARY: dict[str, Any] = {
    "id": 4,
    "form": "sum-of-parts",
    "valuePerShare": 150.0,
    "levels": {"buy": 112.5, "fairLow": 135.0, "fairHigh": 165.0, "trim": 225.0},
    "priceToValue": 1.216,
    "designation": "above",
}


def test_a_row_neither_valued_nor_refused_draws_no_refusal() -> None:
    """A row the meter draws no band for and that has no refusal, a value with no price to draw
    it against, draws neither the meter nor an empty refusal paragraph, and no levels."""
    for changes in ({"price": None}, {"value": None, "levels": None}):
        detail = answers.detail()
        detail["result"] |= changes
        tree = _page("value", detail)
        assert classed(tree, "app-refusal") == []
        assert _meters(tree) == []
        assert classed(tree, "app-company__two") == []
        assert _chip(tree)["props"]["basis"] == "mechanical"


def test_the_basis_chip_follows_the_band_the_meter_draws() -> None:
    """``bandBasis``, the one rule the chip reads: reviewed exactly where the meter and the four
    levels draw a review's band or a secondary valuation's, else mechanical. A review with a
    value and no levels leaves a valued row's mechanical band, and a secondary valuation with no
    levels, or a review's band with no price, draws none: each is mechanical."""
    unlevelled = answers.detail(review=answers.REVIEW | {"levels": None})
    unbanded = answers.refused_detail() | {"secondary": SECONDARY | {"levels": None}}
    unpriced = answers.refused_detail() | {"review": answers.REVIEW}
    unpriced["result"] |= {"price": None}
    cases = [
        (answers.DETAIL, "mechanical", 196.5),
        (answers.reviewed_detail(), "reviewed", 182.0),
        (answers.refused_detail() | {"review": answers.REVIEW}, "reviewed", 182.0),
        (answers.refused_detail() | {"secondary": SECONDARY}, "reviewed", 150.0),
        (unlevelled, "mechanical", 196.5),
        (unbanded, "mechanical", None),
        (unpriced, "mechanical", None),
        (answers.refused_detail(), "mechanical", None),
    ]
    for detail, basis, drawn in cases:
        assert node("bandBasis", [detail]) == basis
        tree = _page("value", detail)
        assert _chip(tree)["props"]["basis"] == basis
        assert [m["props"]["fairValue"] for m in _meters(tree)] == ([drawn] if drawn else [])
    script = _static_file("company_overview.js")
    start = script.index("  function value(")
    assert "P.bandBasis(d)" in script[start : script.index("\n  }\n", start)]


def test_the_value_block_draws_the_same_hover_and_mark() -> None:
    """The Fairband value block draws the drawer's meter and levels (spec 2026-11-19 7.5): on a
    marked row with no review the meter's fair value has the hover as its title, and the Fair
    value row's figure is the value in a span with the same title, the warnings mark before it;
    on a reviewed row the meter's caption has the hover and no mark stands; on a refused row
    neither."""
    marked = answers.detail(warnings=THREE, marked=True)
    tree = _page("value", marked)
    [meter] = _meters(tree)
    assert meter == node("meter", [marked, False])
    assert meter["props"]["fairTitle"] == HOVER
    [figure] = _fact(tree, "Fair value")["props"]["children"]
    assert figure == node("levelRows", [marked])[0][1]
    assert figure == {"type": "span", "props": {"title": HOVER, "children": [MARK, "$196.50"]}}
    assert "figure" in _fact(tree, "Fair value")["props"]["className"].split()
    assert _lists(classed(tree, "app-company__two")[0])[0][0] == ("Fair value", "$196.50")
    assert _marks(tree) == [MARK]

    reviewed = answers.reviewed_detail() | {"warnings": THREE, "marked": False}
    tree = _page("value", reviewed)
    [meter] = _meters(tree)
    assert meter == node("meter", [reviewed, False])
    assert meter["props"]["captionTitle"] == HOVER
    assert "fairTitle" not in meter["props"]
    assert _fact(tree, "Fair value")["props"]["children"] == ["$182.00"]
    assert _marks(tree) == []

    refused = answers.refused_detail() | {"warnings": THREE, "marked": True}
    for detail in (refused, refused | {"review": answers.REVIEW}):
        tree = _page("value", detail)
        assert "Preliminary estimate only" not in json.dumps(tree, ensure_ascii=False)
        assert _marks(tree) == []


def test_the_four_levels_follow_the_value_the_meter_draws() -> None:
    """``levelRows``, the drawer's and the page's one builder of the four levels: the review's
    value and levels where the review counts and has a value, else the snapshot's, its figure the
    mechanical value with its hover; on a refused row the review's or the secondary valuation's
    band the meter draws; none where the meter draws no band."""
    banded = answers.detail()
    banded["result"]["levels"] = {
        "buy": 150.0,
        "fair_low": 168.53,
        "fair_high": 228.02,
        "trim": 294.75,
    }
    # the mechanical value, in a span with its hover, here the note alone (no warning)
    mechanical = {"type": "span", "props": {"title": OPEN_NOTE, "children": [None, "$196.50"]}}
    assert node("levelRows", [banded]) == [
        ["Fair value", mechanical],
        ["Buy level", "$150.00"],
        ["Fair band", "$168.53 – $228.02"],
        ["Trim level", "$294.75"],
    ]
    assert node("levelRows", [answers.reviewed_detail()]) == [
        ["Fair value", "$182.00"],
        ["Buy level", "$145.60"],
        ["Fair band", "$163.80 – $200.20"],
        ["Trim level", "$273.00"],
    ]
    # a review that counts with no value of its own: the snapshot's
    unvalued = answers.detail(review=answers.REVIEW | {"value": None, "levels": None})
    assert node("levelRows", [unvalued])[0] == ["Fair value", mechanical]
    assert node("levelRows", [answers.refused_detail()]) is None
    secondary = answers.refused_detail() | {"secondary": SECONDARY}
    assert node("levelRows", [secondary])[2] == ["Fair band", "$135.00 – $165.00"]
    # no price to draw a band against: no band, no levels
    unpriced = answers.refused_detail() | {"review": answers.REVIEW}
    unpriced["result"] |= {"price": None}
    assert node("levelRows", [unpriced]) is None


# ------------------------------------------------------------------------- the key statistics


TITLES = [
    "Size",
    "Margins",
    "Returns",
    "Valuation",
    "Financial health",
    "Growth, fiscal 2026",
    "Growth a year, per share",
    "Dividends",
]

ROWS = {
    "Size": [
        ("Market cap", "$412.6B"),
        ("Enterprise value", "TWD 12.48T"),
        ("Shares", "2.59B"),
        ("Free float", "88.4%"),
        ("Revenue", "TWD 3.81T"),
        ("Employees", "48,210"),
        ("Beta", "1.18"),
    ],
    "Margins": [
        ("Gross", "59.1%"),
        ("EBITDA", "68.4%"),
        ("Operating", "48.8%"),
        ("Pretax", "50.3%"),
        ("Net", "43.2%"),
    ],
    "Returns": [("ROE", "31.1%"), ("ROA", "20.2%"), ("ROIC", "26.9%"), ("ROCE", "33.4%")],
    "Valuation": [
        ("P/E", "24.6x"),
        ("PEG", "0.88"),
        ("P/B", "6.7x"),
        ("P/S", "10.4x"),
        ("P/FCF", "31.9x"),
        ("EV/Sales", "10.1x"),
        ("EV/EBITDA", "14.8x"),
        ("EV/FCF", "30.7x"),
        ("Earnings yield", "4.1%"),
        ("FCF yield", "3.1%"),
    ],
    "Financial health": [
        ("Debt to equity", "0.21"),
        ("Net debt to EBITDA", "−0.42"),
        ("Current ratio", "2.41"),
        ("Quick ratio", "2.05"),
        ("Interest cover", "126.3x"),
        ("Altman Z", "11.9"),
        ("Piotroski", "7 of 9"),
    ],
    "Growth, fiscal 2026": [
        ("Revenue", "33.8%"),
        ("EBITDA", "30.1%"),
        ("EPS", "40.1%"),
        ("Free cash flow", "22.1%"),
    ],
    "Dividends": [
        ("Yield", "1.37%"),
        ("Payout", "33.2%"),
        ("Dividend a share", "TWD 19.50"),
        ("Paid", "Quarterly"),
        ("Last payment", "9 Oct 2026"),
    ],
}

PER_SHARE = [
    ["", "3Y", "5Y", "10Y"],
    ["Revenue", "25.0%", "23.5%", "17.7%"],
    ["Net income", "28.5%", "27.8%", "22.0%"],
    ["Cash flow", "23.3%", "21.6%", "17.4%"],
    ["Dividend", "12.3%", "12.2%", "10.0%"],
]


def _groups(tree: Any) -> dict[str, Any]:
    """Each group of ``tree`` by its title."""
    return {
        text(classed(g, "app-company__grouptitle")[0]): g
        for g in classed(tree, "app-company__group")
    }


def _table(tree: Any) -> list[list[str]]:
    """The texts of the one small table of ``tree``: its head's cells, then each row's."""
    [table] = [e for e in elements(tree) if e.get("type") == "table"]
    head = [text(e) for e in elements(table) if e.get("type") == "th"]
    rows = [e for e in elements(table) if e.get("type") == "tr"][1:]
    return [head] + [[text(e) for e in elements(row) if e.get("type") == "td"] for row in rows]


def test_the_statistics_groups_rows_and_figures() -> None:
    """The caption in the block's head; eight groups in three columns, Size, Margins and Returns
    in the first, Valuation and Financial health in the second, the two growth groups and
    Dividends in the third; the growth group's title names the answer's fiscal year; every row's
    name and figure, the yearly rates a share in a small table."""
    tree = _page("statistics", _with(growth={"fiscalYear": 2026}))
    assert tree.get("type") == "section"
    [title] = [e for e in elements(tree) if e.get("type") == "h2"]
    assert text(title) == "Key statistics"
    [caption] = classed(tree, "app-company__note")
    assert caption["props"]["className"] == "caption app-company__note"
    assert text(caption) == "trailing twelve months, unless the row says"
    [three] = classed(tree, "app-company__three")
    columns = classed(three, "app-company__stack")
    assert [list(_groups(column)) for column in columns] == [TITLES[:3], TITLES[3:5], TITLES[5:]]
    groups = _groups(tree)
    assert list(groups) == TITLES
    for name, rows in ROWS.items():
        assert _lists(groups[name]) == [rows], name
    assert _table(groups["Growth a year, per share"]) == PER_SHARE
    # the table's rates in figure-sm, so twelve of them fit a column of three (the decision log
    # of 2026-11-17); its rows' names in body, as every table's
    cells = [e for e in elements(groups["Growth a year, per share"]) if e.get("type") == "td"]
    assert {c["props"]["className"] for c in cells} == {"body app-company__rowname", "figure-sm"}
    # words in body, figures in figure: Paid is the frequency's word
    assert "body" in _fact(groups["Dividends"], "Paid")["props"]["className"].split()
    assert "figure" in _fact(groups["Dividends"], "Yield")["props"]["className"].split()


def test_the_growth_group_without_a_fiscal_year() -> None:
    titles = list(_groups(_page("statistics", _with(growth={"fiscalYear": None}))))
    assert titles[5] == "Growth, last fiscal year"
    assert list(_groups(_page("statistics", answers.OVERVIEW)))[5] == "Growth, fiscal 2025"


def test_a_reporting_currency_figure_carries_its_code() -> None:
    """Enterprise value, revenue and the dividend a share are in the reporting currency, with its
    code in the dollar sign's place; market cap is in US dollars."""
    answer = _with(
        size={
            "enterpriseValue": {"value": 4.94e12, "currency": "TWD"},
            "revenue": {"value": 478.8e9, "currency": "USD"},
        }
    )
    groups = _groups(_page("statistics", answer))
    assert text(_fact(groups["Size"], "Enterprise value")) == "TWD 4.94T"
    assert text(_fact(groups["Size"], "Revenue")) == "$478.8B"
    assert text(_fact(groups["Size"], "Market cap")) == "$412.6B"
    assert text(_fact(groups["Dividends"], "Dividend a share")) == "TWD 19.50"


def _figures(tree: Any) -> list[str]:
    """The text of every figure of ``tree``: each list's and each table cell's but the rows'
    names."""
    cells = [
        e
        for e in elements(tree)
        if e.get("type") == "td" and "app-company__rowname" not in e["props"]["className"]
    ]
    return [text(e) for e in classed(tree, "app-kv__v") + cells]


def test_every_figure_missing_draws_the_dash() -> None:
    """A company with nothing stored, not even its profile: no exception, and the dash in every
    row of Company and of Key statistics, the growth group named for the last fiscal year; the
    brief is not drawn."""
    empty = answers.empty_overview()
    company = _page("Company", {"company": empty["company"]})
    assert classed(company, "app-company__brief") == []
    assert classed(company, "app-company__more") == []
    assert [figure for rows in _lists(company) for _, figure in rows] == ["—"] * 8
    assert _links(company) == []
    tree = _page("statistics", empty)
    figures = _figures(tree)
    assert len(figures) == 7 + 5 + 4 + 10 + 7 + 4 + 12 + 5
    assert set(figures) == {"—"}
    assert list(_groups(tree))[5] == "Growth, last fiscal year"
    facts = _page("priceFacts", empty)
    assert [figure for rows in _lists(facts) for _, figure in rows] == ["—"] * (9 + 6 + 4)
    drawn = _page("draw.overview", empty, answers.DETAIL)
    assert drawn["props"]["className"] == "app-company__grid"
    [news] = [e for e in elements(drawn) if e.get("type") == "section" and _title(e) == "News"]
    assert _stories(news) == []
    assert "0 stories" in _head_texts(news)


def test_a_company_with_a_profile_and_nothing_else() -> None:
    """Review Focus 2: the profile's facts and the brief are drawn; every statistic the profile
    does not give is the dash, every price fact but the profile's average volume too, and News
    draws its empty list and its count."""
    answer = answers.profile_only_overview()
    company = _page("Company", {"company": answer["company"]})
    assert text(classed(company, "app-company__brief")[0]) == COMPANY["brief"]
    assert text(_fact(company, "Employees")) == "48,210"
    groups = _groups(_page("statistics", answer))
    for title, group in groups.items():
        for name, figure in [row for rows in _lists(group) for row in rows]:
            given = {"Employees": "48,210", "Beta": "1.18"}.get(name) if title == "Size" else None
            assert figure == (given or "—"), (title, name)
    rates = _table(groups["Growth a year, per share"])[1:]
    assert {cell for row in rates for cell in row[1:]} == {"—"}
    for name, figure in [row for rows in _lists(_page("priceFacts", answer)) for row in rows]:
        assert figure == ("9.4M" if name == "Average volume" else "—"), name
    news = _page("news", {"stories": answer["news"]["stories"], "note": None})
    assert _stories(news) == []
    assert "0 stories" in _head_texts(news)


def test_interest_cover_at_zero_is_the_dash() -> None:
    """The interest cover and a multiple at exactly 0 are the dash; a ratio drawn as a plain
    number at 0 is its zero."""
    groups = _groups(
        _page(
            "statistics",
            _with(health={"interestCover": 0, "debtToEquity": 0}, valuation={"pe": 0}),
        )
    )
    assert text(_fact(groups["Financial health"], "Interest cover")) == "—"
    assert text(_fact(groups["Valuation"], "P/E")) == "—"
    assert text(_fact(groups["Financial health"], "Debt to equity")) == "0.00"


# --------------------------------------------------------------------------------- the tab


def test_the_overview_draws_two_columns_with_three_blocks_in_each() -> None:
    """``draw.overview``: the grid of two columns; at the left, in order, Company on the answer's
    company, Fairband value on the detail and Key statistics on the answer; at the right the price
    chart on the answer's prices, keyed on the company, so each company's chart opens at the past
    year with no day picked, then Price facts on the answer and News on the answer's stories and
    the note the page sets on them. Both columns are the page's plain column (8.7): Key
    statistics, the left one's last block, is a block the rule that grows a column's last block
    selects, so it grows where the right column is the taller; News, the right one's last block,
    fills what is left instead."""
    tree = _page("draw.overview", answers.OVERVIEW, answers.DETAIL)
    assert tree["props"]["className"] == "app-company__grid"
    left, right = tree["props"]["children"]
    assert left["props"]["className"] == "app-company__col"
    assert right["props"]["className"] == "app-company__col"
    company, value, statistics = left["props"]["children"]
    assert company["props"]["company"] == answers.OVERVIEW["company"]
    assert value == _page("value", answers.DETAIL)
    assert statistics == _page("statistics", answers.OVERVIEW)
    assert statistics["type"] == "section"
    assert statistics["props"]["className"].split() == ["app-company__panel"]
    chart, facts, news = right["props"]["children"]
    assert chart["props"]["prices"] == answers.OVERVIEW["prices"]
    assert chart["props"]["key"] == "price " + answers.SYMBOL
    assert facts == _page("priceFacts", answers.OVERVIEW)
    assert news == _page("news", {"stories": STORIES, "note": None})
    assert news["props"]["className"].split() == ["app-company__panel", "app-company__panel--fill"]
    script = _static_file("company_overview.js")
    start = script.index("  function overview(")
    assert "h(P.companyChart.Chart, {" in script[start : script.index("\n  }\n", start)]
    noted = answers.OVERVIEW | {"news": answers.OVERVIEW["news"] | {"note": "no FMP key"}}
    drawn = _page("draw.overview", noted, answers.DETAIL)["props"]["children"][1]
    assert drawn["props"]["children"][2] == _page(
        "news", {"stories": STORIES, "note": "no FMP key"}
    )


# ----------------------------------------------------------------------------- price facts


TRADING = answers.OVERVIEW["trading"] | {
    "dayLow": {"value": 355.75, "currency": "USD"},
    "dayHigh": {"value": 360.83, "currency": "USD"},
    "nextEarnings": "2027-02-04",
}
CHANGE = answers.OVERVIEW["priceChange"] | {"d1": 1.2, "d5": -0.7, "y10": 1186.6}


def test_the_three_groups_of_price_facts() -> None:
    """Three groups side by side (8.5), in the Words table's order: Trading, from the quote's row,
    its money to cents, a range's two ends, the volumes compact as bare counts and the next
    earnings date; Price change and Price change, years, each a percent as given to one decimal
    with its sign, in the text's own colour. No chip, no cite, no vendor named."""
    tree = _page("priceFacts", answers.OVERVIEW | {"trading": TRADING, "priceChange": CHANGE})
    assert tree.get("type") == "section"
    assert _title(tree) == "Price facts"
    [three] = classed(tree, "app-company__three")
    groups = _groups(three)
    assert list(groups) == ["Trading", "Price change", "Price change, years"]
    assert _lists(groups["Trading"]) == [
        [
            ("Open", "$180.10"),
            ("Previous close", "$180.25"),
            ("Day range", "$355.75 – $360.83"),
            ("52 weeks", "$121.75 – $201.30"),
            ("50-day average", "$176.88"),
            ("200-day average", "$158.42"),
            ("Volume", "8.1M"),
            ("Average volume", "9.4M"),
            ("Next earnings", "4 Feb 2027"),
        ]
    ]
    assert _lists(groups["Price change"]) == [
        [
            ("1 day", "+1.2%"),
            ("5 days", "−0.7%"),
            ("1 month", "+6.4%"),
            ("3 months", "+12.9%"),
            ("6 months", "+21.3%"),
            ("Year to date", "+32.3%"),
        ]
    ]
    assert _lists(groups["Price change, years"]) == [
        [
            ("1 year", "+41.9%"),
            ("3 years", "+168.2%"),
            ("5 years", "+244.9%"),
            ("10 years", "+1,186.6%"),
        ]
    ]
    # every figure in figure and nothing else: no class colours a change by its sign
    assert {e["props"]["className"] for e in classed(tree, "app-kv__v")} == {"figure app-kv__v"}
    assert [e for e in elements(tree) if "basis" in e["props"] or "principal" in e["props"]] == []


def test_a_range_with_an_end_missing_and_a_change_of_nothing() -> None:
    """A range is the dash where either end is missing; a change that is zero at one decimal
    carries no sign; a missing change or date is the dash."""
    trading = TRADING | {"dayHigh": None, "yearLow": {"value": None, "currency": "USD"}}
    change = CHANGE | {"d1": 0, "d5": -0.04, "m1": None}
    groups = _groups(
        _page(
            "priceFacts",
            answers.OVERVIEW | {"trading": trading | {"nextEarnings": None}, "priceChange": change},
        )
    )
    assert text(_fact(groups["Trading"], "Day range")) == "—"
    assert text(_fact(groups["Trading"], "52 weeks")) == "—"
    assert text(_fact(groups["Trading"], "Next earnings")) == "—"
    assert text(_fact(groups["Price change"], "1 day")) == "0.0%"
    assert text(_fact(groups["Price change"], "5 days")) == "0.0%"
    assert text(_fact(groups["Price change"], "1 month")) == "—"


# -------------------------------------------------------------------------------------- news


STORIES = answers.OVERVIEW["news"]["stories"]


def _title(tree: Any) -> str:
    """The text of the block's title, its head's ``h2``."""
    [title] = [e for e in elements(tree) if e.get("type") == "h2"]
    return text(title)


def _head_texts(tree: Any) -> list[str]:
    """The text of each paragraph in the block's head."""
    [head] = [e for e in elements(tree) if e.get("type") == "header"]
    return [text(e) for e in elements(head) if e.get("type") == "p"]


def _stories(tree: Any) -> list[tuple[str, str, str | None]]:
    """Each story of the news list: its day, its title and its publisher, None for none."""
    [found] = classed(tree, "app-company__news")
    return [
        (
            text(classed(item, "app-company__newsday")[0]),
            text(classed(item, "app-company__newstitle")[0]),
            text(by[0]) if (by := classed(item, "app-company__newsby")) else None,
        )
        for item in elements(found)
        if item.get("type") == "li"
    ]


def test_the_news_list_and_its_count() -> None:
    """News (8.6): the block that fills what its column leaves (8.7), the count in its head; every
    story, newest first: its day, its title, its publisher under it, the site where FMP names no
    publisher. The list is a region the keyboard can reach and scroll."""
    tree = _page("news", {"stories": STORIES, "note": None})
    assert tree.get("type") == "section"
    assert tree["props"]["className"] == "app-company__panel app-company__panel--fill"
    assert _title(tree) == "News"
    assert _head_texts(tree) == ["3 stories"]
    [count] = [e for e in classed(tree, "caption") if text(e) == "3 stories"]
    assert count["props"]["className"] == "caption app-company__note"
    [found] = classed(tree, "app-company__news")
    assert (found["type"], found["props"]["tabIndex"]) == ("ul", 0)
    assert _stories(tree) == [
        (
            "13 Nov 2026",
            "Lanternfield Optics lifts its lens output for car makers",
            "Harbor Street Journal",
        ),
        ("12 Nov 2026", "Three lens makers to watch", "lensdaily.example"),
        ("10 Nov 2026", "Lanternfield Optics' October sales", "Quayside Markets"),
    ]
    [day] = classed(tree, "app-company__newsday")[:1]
    assert day["props"]["className"] == "figure-sm app-company__newsday"
    [by] = classed(tree, "app-company__newsby")[:1]
    assert by["props"]["className"] == "caption app-company__newsby"
    one = _page("news", {"stories": STORIES[:1], "note": None})
    assert _head_texts(one) == ["1 story"]
    # a story with no day, title or publisher: the dash for the day and the title, no line under
    bare = _page(
        "news", {"stories": [{"day": None, "title": None, "publisher": None, "url": None}]}
    )
    assert _stories(bare) == [("—", "—", None)]


def test_a_story_is_a_link_only_when_its_address_is_a_web_address() -> None:
    """10.6 and Review Focus 4: a title is a link that opens in a new tab with no opener and no
    referrer only where its address is http or https; any other address, empty or missing, and
    its title is text."""
    for url in ("https://harborstreet.example/a", "http://lensdaily.example/b?c=1"):
        tree = _page("news", {"stories": [STORIES[0] | {"url": url}], "note": None})
        [link] = _links(tree)
        assert link["props"]["className"] == "body app-company__newstitle"
        assert link["props"]["href"] == url
        assert link["props"]["target"] == "_blank"
        assert link["props"]["rel"] == "noopener noreferrer"
        assert text(link) == STORIES[0]["title"]
    for url in ("javascript:alert(1)", " javascript:alert(1)", "data:text/html,<b>x</b>", "", None):
        tree = _page("news", {"stories": [STORIES[0] | {"url": url}], "note": None})
        assert _links(tree) == []
        [title] = classed(tree, "app-company__newstitle")
        assert (title["type"], title["props"]["className"]) == (
            "span",
            "body app-company__newstitle",
        )
        assert "href" not in title["props"]
        assert text(title) == STORIES[0]["title"]
    # the stored third story's address is javascript:
    assert len(_links(_page("news", {"stories": STORIES, "note": None}))) == 2


def test_the_news_note_is_drawn_when_given() -> None:
    """10.5: where the second read failed, one caption in the block's head, after the count, says
    so with the server's sentence; the stored stories stay. None without a note."""
    tree = _page("news", {"stories": STORIES, "note": "no FMP key"})
    assert _head_texts(tree) == ["3 stories", "newer news did not load: no FMP key"]
    [note] = [e for e in classed(tree, "caption") if text(e).startswith("newer news")]
    assert note["props"]["className"] == "caption app-company__note"
    assert len(_stories(tree)) == 3
    assert "newer news" not in text(_page("news", {"stories": STORIES, "note": None}))


def test_no_news_draws_an_empty_list_and_its_count() -> None:
    tree = _page("news", {"stories": [], "note": None})
    assert _head_texts(tree) == ["0 stories"]
    assert _stories(tree) == []
    [found] = classed(tree, "app-company__news")
    assert found["type"] == "ul"


TYPE_STYLES = {"heading", "body", "caption", "figure-sm"}  # the design system's, which it shares


def test_the_news_classes_are_the_company_page_s_alone() -> None:
    """Every class the News block draws but the design system's type styles is the company
    page's own: under its prefix, and in no script but the company page's, so none of the block's
    rules can style an element another view draws; and no rule of the page's styles names
    ``app-news``, the class of the drawer's News items section before it left the drawer."""
    linked = STORIES[0] | {"url": "https://harborstreet.example/a"}
    tree = _page("news", {"stories": [linked, STORIES[2]], "note": "no FMP key"})
    drawn = {
        name for e in elements(tree) for name in str(e["props"].get("className") or "").split()
    }
    own = drawn - TYPE_STYLES
    news = {"__news", "__newshead", "__newsday", "__newstitle", "__newsby"}
    assert {"app-company" + part for part in news} <= own
    page = {
        "company.js",
        "company_overview.js",
        "company_chart.js",
        "company_estimates.js",
        "company_financials.js",
        "company_financials_chart.js",
        "company_investor.js",
    }
    scripts = {
        p.name: p.read_text(encoding="utf-8") for p in STATIC.rglob("*.js") if p.name not in page
    }
    assert {"app.js", "report_parts.js", "inbox.js", "charts.js", "bundle.js"} <= set(scripts)
    for name in sorted(own):
        assert name.startswith("app-company__"), name
        assert [script for script, body in scripts.items() if name in body] == [], name
    assert re.search(r"\.app-news\b", _static_file("index.html")) is None


# ---------------------------------------------------------------------------- the second read


def _function_source(script: str, name: str) -> str:
    """The whole text of the script's ``function <name>(``, its braces matched."""
    start = script.index(f"  function {name}(")
    depth = 0
    for at in range(script.index("{", start), len(script)):
        depth += {"{": 1, "}": -1}.get(script[at], 0)
        if depth == 0:
            return script[start : at + 1]
    raise AssertionError(name)


def _run(source: str, *args: Any) -> Any:
    """What a node script writes as JSON, given ``args`` as JSON in its argv."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, "-e", source] + [json.dumps(arg) for arg in args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


# A fetch that answers each call with the next of the given answers and keeps the calls: an
# answer is {status, body}, its body JSON or absent (a body that is not JSON), or {fails}, a
# request that never reached the server.
FETCH = """
var calls = [];
var given = JSON.parse(process.argv[1]);
function fetch(url, init) {
  var a = given[calls.length];
  calls.push({ url: url, init: init });
  if (a.fails) return Promise.reject(new TypeError(a.fails));
  return Promise.resolve({
    ok: a.status >= 200 && a.status < 300, status: a.status,
    json: function () {
      return 'body' in a ? Promise.resolve(a.body) : Promise.reject(new SyntaxError('not JSON'));
    }
  });
}
"""


def _fresh(answer: dict[str, Any], symbol: str = answers.SYMBOL, limit: int = 60) -> Any:
    """``freshNews(symbol, limit)`` of company.js on one answer of the pass-through: its stories
    or its error's message, and the fetch's calls."""
    script = _static_file("company.js")
    names = ("freshNews", "refused", "newsStories", "words")
    source = "\n".join(
        [FETCH]
        + [_function_source(script, name) for name in names]
        + [
            "freshNews.apply(null, JSON.parse(process.argv[2])).then(",
            "  function (stories) { return { stories: stories }; },",
            "  function (err) { return { error: err.message }; }",
            ").then(function (got) {",
            "  got.calls = calls;",
            "  process.stdout.write(JSON.stringify(got));",
            "});",
        ]
    )
    return _run(source, [answer], [symbol, limit])


NEWS_PAYLOAD: list[Any] = [
    *payloads.NEWS,
    {"publishedDate": "2026-11-09T07:00:00.000Z", "site": "  quayside.example ", "title": " "},
    {"publishedDate": "9 Nov 2026", "publisher": None, "url": 42},
    {},
    "a row that is not an object",
    None,
    ["neither is this"],
]


def test_fresh_news_reads_the_pass_through_and_shapes_its_stories_as_the_read_does() -> None:
    """``freshNews`` asks the news pass-through with the header a write carries, the symbol
    encoded and the limit given, and answers its payload's stories in the overview read's shape:
    each object row in its order, the same as ``page_fmp.stories`` gives on that payload."""
    got = _fresh(
        {"status": 200, "body": {"responseId": 9, "reused": False, "payload": NEWS_PAYLOAD}}
    )
    assert got["stories"] == page_fmp.stories(NEWS_PAYLOAD)
    assert got["stories"][:3] == STORIES
    assert got["calls"] == [
        {
            "url": "/api/vendor/news/LFOX?limit=60",
            "init": {"headers": {"X-Fairband-Request": "1"}},
        }
    ]
    for symbol, path in (("BRK.B", "BRK.B"), ("A&B", "A%26B")):
        got = _fresh({"status": 200, "body": {"payload": []}}, symbol, 25)
        assert got["stories"] == []
        assert got["calls"][0]["url"] == f"/api/vendor/news/{path}?limit=25"


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        ({"status": 503, "body": {"detail": "no FMP key"}}, "no FMP key"),
        (
            {
                "status": 503,
                "body": {
                    "detail": "the pass-throughs are busy: four calls are in flight, try again"
                },
            },
            "the pass-throughs are busy: four calls are in flight, try again",
        ),
        ({"status": 502, "body": {"detail": "FMP answered 500"}}, "FMP answered 500"),
        ({"status": 500}, "the server answered 500"),
        ({"fails": "Failed to fetch"}, "Failed to fetch"),
        # FMP's error body, which the pass-through answers with a 200 and stores as unusable
        (
            {"status": 200, "body": {"payload": {"Error Message": "Limit Reach ."}}},
            "the answer held no stories",
        ),
        ({"status": 200, "body": {"payload": None}}, "the answer held no stories"),
        ({"status": 200, "body": None}, "the answer held no stories"),
        # a 200 whose body is not JSON: the same sentence, not the parser's
        ({"status": 200}, "the answer held no stories"),
    ],
)
def test_fresh_news_refused_is_the_server_s_sentence(answer: dict[str, Any], error: str) -> None:
    assert _fresh(answer)["error"] == error


# The second read's shell, run on a state the test gives it: freshNews answers what the plan
# says once the plan's move is made, and the script writes what the page holds after.
NEWER = """
var plan = JSON.parse(process.argv[1]);
var state = { answers: { overview: plan.answer } };
var renders = 0;
function render() { renders++; }
var asked = [];
var settle = null;
function freshNews(symbol, limit) {
  asked.push([symbol, limit]);
  return new Promise(function (resolve, reject) { settle = { resolve: resolve, reject: reject }; });
}
"""

NEWER_RUN = """
newer(plan.symbol, plan.answer);
if (plan.move === 'company') state.answers = { overview: plan.other };
if (plan.move === 'reread') state.answers = { overview: JSON.parse(JSON.stringify(plan.answer)) };
if (plan.move === 'tab') state.answers.estimates = { symbol: plan.symbol };
if (settle && plan.error) settle.reject(new Error(plan.error));
else if (settle) settle.resolve(plan.stories);
setTimeout(function () {
  process.stdout.write(JSON.stringify({
    asked: asked, renders: renders, answers: state.answers
  }));
}, 0);
"""


def _newer(answer: dict[str, Any], **plan: Any) -> Any:
    script = _static_file("company.js")
    source = "\n".join([NEWER, _function_source(script, "newer"), NEWER_RUN])
    return _run(source, {"symbol": answer["symbol"], "answer": answer} | plan)


STALE = answers.OVERVIEW | {"news": answers.OVERVIEW["news"] | {"stale": True}}
FRESH = [
    {
        "day": "2026-11-17",
        "title": "Lanternfield Optics opens a lens plant",
        "publisher": "Harbor Street Journal",
        "url": "https://harborstreet.example/plant",
    }
]


def test_stale_news_is_asked_for_once_and_drawn_in_the_stored_ones_place() -> None:
    """10.5: where the stored news is stale, the page asks the pass-through once, at the answer's
    limit, and draws its stories in the stored ones' place: the answer it holds gets them and no
    note, every other part as the read gave it."""
    got = _newer(STALE, stories=FRESH)
    assert got["asked"] == [[answers.SYMBOL, 60]]
    assert got["renders"] == 1
    held = got["answers"]["overview"]
    assert held["news"] == STALE["news"] | {"stories": FRESH, "note": None}
    assert {k: v for k, v in held.items() if k != "news"} == {
        k: v for k, v in STALE.items() if k != "news"
    }
    # the reader went to another tab of the company: the answer is held, and the stories land
    moved = _newer(STALE, stories=FRESH, move="tab")
    assert moved["answers"]["overview"]["news"]["stories"] == FRESH
    assert moved["renders"] == 1


def test_a_refused_second_read_keeps_the_stored_stories_and_sets_the_note() -> None:
    got = _newer(STALE, error="no FMP key")
    assert got["asked"] == [[answers.SYMBOL, 60]]
    assert got["answers"]["overview"]["news"] == STALE["news"] | {"note": "no FMP key"}
    assert got["renders"] == 1


def test_news_not_stale_is_not_asked_for() -> None:
    got = _newer(answers.OVERVIEW, stories=FRESH)
    assert got["asked"] == []
    assert got["renders"] == 0
    assert got["answers"]["overview"] == answers.OVERVIEW


def test_a_second_read_that_lands_after_the_page_moved_on_is_dropped() -> None:
    """The reader went to another company, or the page read the company anew: the answer the read
    was asked for is no longer held, so its stories and its note are dropped and nothing draws."""
    other = answers.OVERVIEW | {"symbol": "BRK.B"}
    # the read anew holds another answer of the company, its stored stories and no note
    for move, held in (("company", other), ("reread", STALE)):
        for outcome in ({"stories": FRESH}, {"error": "no FMP key"}):
            got = _newer(STALE, move=move, other=other, **outcome)
            assert got["answers"] == {"overview": held}
            assert got["renders"] == 0


def test_the_second_read_runs_once_for_each_read_of_the_overview() -> None:
    """The page asks for newer news as an Overview's read lands, after it draws the stored stories,
    and not when it shows a tab it holds; so not again on a return to the Overview, and again after
    the page reads anew."""
    script = _static_file("company.js")
    start = script.index("  function load(")
    load = script[start : script.index("\n  }\n", start)]
    assert load.count("newer(") == 1
    shortcut = load[: load.index("var whole =")]
    assert "newer(" not in shortcut
    landed = load[load.index(".then(function (found) {") : load.index(".catch(")]
    assert landed.index("shown();") < landed.index(
        "if (want.tab === 'overview' && found.answer) newer(want.symbol, found.answer);"
    )


# ---------------------------------------------------------------------------- the columns


def _top_rule(selector: str) -> str:
    """The declarations of the page's one rule outside an at-rule whose line opens with
    ``selector``, on one line."""
    css = _static_file("index.html")
    ends = [m.end() for m in re.finditer(r"(?m)^  " + re.escape(selector), css)]
    assert len(ends) == 1, selector
    return " ".join(css[ends[0] : css.index("}", ends[0])].split())


def test_the_columns_rule_is_in_the_page_s_css() -> None:
    """8.7 and 9, both ways (the decision log of 2026-11-17): the grid stretches both columns to
    the row's height, which the taller column sets. The news list has no height of its own, so
    its stories never size the row: on the Overview the right column's least height is the
    chart, Price facts and News at its floor of 260px. Where the left column is the taller, News
    fills what is left, its list scrolling inside it; where the right column is, the left
    column's last block grows to the row; on every other tab the last block of each column grows
    to the row. Under 1180px one column, the right column's blocks after the left's, the news
    list as tall as its stories under 520px."""
    grid = _top_rule(".app-company__grid {")
    assert "align-items: stretch;" in grid and "align-items: start" not in grid
    # no column adds no height of its own: the rule that made the left column alone set the row
    # is gone, from the page's CSS and from the Overview's script
    assert "app-company__col--match" not in _static_file("index.html")
    assert "app-company__col--match" not in _static_file("company_overview.js")
    fill = _top_rule(".app-company__panel--fill {")
    for part in ("display: flex;", "flex-direction: column;", "flex: 1 1 0;", "min-height: 260px;"):
        assert part in fill
    # each declaration whole, so `height: 0` is not found inside `min-height: 0`
    news = {part.strip() for part in _top_rule(".app-company__news {").split(";")}
    assert {"flex: 1 1 0", "height: 0", "min-height: 0", "overflow-y: auto"} <= news
    grows = ".app-company__col > .app-company__panel:last-child:not(.app-company__panel--fill) {"
    assert _top_rule(grows) == "flex: 1 1 auto;"
    html = _static_file("index.html")
    narrow = re.search(r"\n  @media \(width < 1180px\) \{\n(.*?)\n  \}\n", html, re.DOTALL)
    assert narrow is not None
    rules = [" ".join(line.split()) for line in narrow[1].splitlines()]
    assert rules == [
        ".app-company__grid { grid-template-columns: minmax(0, 1fr); }",
        ".app-company__panel--fill { flex: none; }",
        ".app-company__news { flex: none; height: auto; max-height: 520px; }",
    ]
    assert html.count("@media (width < 1180px)") == 1
    assert ".app-company__news:focus-visible {" in html


def test_the_script_and_the_columns_inside_a_block() -> None:
    """The tab's script loads after company.js. Inside a block, three columns become two under
    810px of the block's width (the decision log of 2026-11-17: the least width of the table of
    yearly rates a share, at three negative three-figure rates a row, in three columns with their
    gaps) and one under 460px; two columns become one there too."""
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert scripts.index("company_overview.js") == scripts.index("company.js") + 1
    for name, columns in (("two", "minmax(0, 1fr) minmax(0, 1fr)"), ("three", "repeat(3,")):
        [rule] = re.findall(r"\n  \.app-company__" + name + r" \{([^}]*)\}", html)
        assert "grid-template-columns: " + columns in " ".join(rule.split())
    assert "@container (width < 700px)" not in html
    narrow = re.search(r"@container \(width < 810px\) \{([^}]*)\}", html)
    assert narrow is not None
    assert ".app-company__three { grid-template-columns: repeat(2, minmax(0, 1fr));" in narrow[1]
    narrower = re.search(r"@container \(width < 460px\) \{([^}]*)\}", html)
    assert narrower is not None
    assert ".app-company__two, .app-company__three" in narrower[1]
    assert "grid-template-columns: minmax(0, 1fr);" in narrower[1]


def test_a_block_in_two_columns_ends_its_halves_near_one_another() -> None:
    """The two-column form of a block, from 460px to under 810px of its width (the decision log of
    2026-11-17), lays out what would wrap under its first column alone. Key statistics' third
    stack spans both columns and lays its groups out in them, Growth beside the yearly rates a
    share, which span two rows, so Dividends sits under Growth; Price facts' first group, Trading,
    spans two rows beside the two price changes, one under the other. The rules reach those
    alone: Key statistics' grid holds three stacks, the third's second group the yearly rates;
    Price facts' grid holds three groups and no stack. The three-column form and the one-column
    form keep their rules."""
    html = _static_file("index.html")
    found = re.search(
        r"\n  @container \(460px <= width < 810px\) \{\n(.*?)\n  \}\n", html, re.DOTALL
    )
    assert found is not None
    assert html.count("@container (460px <= width < 810px)") == 1
    assert html.index("@container (width < 810px)") < found.start()
    assert found.start() < html.index("@container (width < 460px)")
    rules = re.findall(r"([^{}]+)\{([^}]*)\}", found[1])
    stack = ".app-company__three > .app-company__stack:last-child"
    spread = (
        "display: grid; grid-column: 1 / -1; grid-template-columns: repeat(2, minmax(0, 1fr));"
        " gap: var(--space-4) var(--space-8); align-items: start;"
    )
    spans = f"{stack} > :nth-child(2), .app-company__three > .app-company__group:first-child"
    assert [(" ".join(s.split()), " ".join(b.split())) for s, b in rules] == [
        (stack, spread),
        (spans, "grid-row: span 2;"),
    ]
    [stats] = classed(_page("statistics", answers.OVERVIEW), "app-company__three")
    stacks = stats["props"]["children"]
    assert [s["props"]["className"] for s in stacks] == ["app-company__stack"] * 3
    # the stack's children, as React flattens the list it is handed into the element's children
    [third] = stacks[2]["props"]["children"]
    assert [g["props"]["className"] for g in third] == ["app-company__group"] * 3
    assert [text(classed(g, "app-company__grouptitle")[0]) for g in third] == [
        "Growth, fiscal 2025",
        "Growth a year, per share",
        "Dividends",
    ]
    [facts] = classed(_page("priceFacts", answers.OVERVIEW), "app-company__three")
    groups = facts["props"]["children"]
    assert [g["props"]["className"] for g in groups] == ["app-company__group"] * 3
    assert text(classed(groups[0], "app-company__grouptitle")[0]) == "Trading"
