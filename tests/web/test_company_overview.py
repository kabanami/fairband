"""The company page's Overview tab, its left column (the company page's design, 8.1 to 8.3): the
Company block, the Fairband value block and the Key statistics block, and the tab's function that
draws them, with the price chart first in its right column (``test_company_chart``).
company.js, company_overview.js and company_chart.js run in node after the bundle and app.js
(``support.page``), and the tests read the trees their builders return.

The company is ``page_answers``' LFOX: valued at $196.50 against a price of $182.40, its levels
$147.38, $176.85 to $216.15 and $294.75; reporting in New Taiwan dollars, so its enterprise value,
its revenue and its dividend a share carry the code TWD."""

import re
from typing import Any

import pytest
from support import page_answers as answers
from support.page import NODE, STATIC, classed, elements, node, text
from support.web import _static_file

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
    The published report's line stands under a rule: the stance chip in the drawer's classes, the
    mode and the day, the principal chip, and the link to the report page."""
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
    assert link["props"]["href"] == "#report/LFOX"
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
    assert link["props"]["href"] == "#report/A%26B"


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


def test_the_four_levels_follow_the_value_the_meter_draws() -> None:
    """``levelRows``, the drawer's and the page's one builder of the four levels: the review's
    value and levels where the review counts and has a value, else the snapshot's; on a refused
    row the review's or the secondary valuation's band the meter draws; none where the meter
    draws no band."""
    banded = answers.detail()
    banded["result"]["levels"] = {
        "buy": 150.0,
        "fair_low": 168.53,
        "fair_high": 228.02,
        "trim": 294.75,
    }
    assert node("levelRows", [banded]) == [
        ["Fair value", "$196.50"],
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
    assert node("levelRows", [unvalued])[0] == ["Fair value", "$196.50"]
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
    cells = [e for e in classed(tree, "figure") if e.get("type") == "td"]
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
    drawn = _page("draw.overview", empty, answers.DETAIL)
    assert drawn["props"]["className"] == "app-company__grid"


def test_a_company_with_a_profile_and_nothing_else() -> None:
    """Review Focus 2: the profile's facts and the brief are drawn; every statistic the profile
    does not give is the dash."""
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


def test_the_overview_draws_two_columns_with_the_three_blocks_at_the_left() -> None:
    """``draw.overview``: the grid of two columns; at the left, in order, Company on the answer's
    company, Fairband value on the detail and Key statistics on the answer; at the right first
    the price chart on the answer's prices, keyed on the company, so each company's chart opens
    at the past year with no day picked."""
    tree = _page("draw.overview", answers.OVERVIEW, answers.DETAIL)
    assert tree["props"]["className"] == "app-company__grid"
    left, right = tree["props"]["children"]
    assert left["props"]["className"] == "app-company__col"
    assert right["props"]["className"].split()[0] == "app-company__col"
    company, value, statistics = left["props"]["children"]
    assert company["props"]["company"] == answers.OVERVIEW["company"]
    assert value == _page("value", answers.DETAIL)
    assert statistics == _page("statistics", answers.OVERVIEW)
    chart = right["props"]["children"][0]
    assert chart["props"]["prices"] == answers.OVERVIEW["prices"]
    assert chart["props"]["key"] == "price " + answers.SYMBOL
    script = _static_file("company_overview.js")
    start = script.index("  function overview(")
    assert "h(P.companyChart.Chart, {" in script[start : script.index("\n  }\n", start)]


def test_the_script_and_the_columns_inside_a_block() -> None:
    """The tab's script loads after company.js. Inside a block, three columns become two under
    700px of the block's width and one under 460px; two columns become one there too."""
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert scripts.index("company_overview.js") == scripts.index("company.js") + 1
    for name, columns in (("two", "minmax(0, 1fr) minmax(0, 1fr)"), ("three", "repeat(3,")):
        [rule] = re.findall(r"\n  \.app-company__" + name + r" \{([^}]*)\}", html)
        assert "grid-template-columns: " + columns in " ".join(rule.split())
    narrow = re.search(r"@container \(width < 700px\) \{([^}]*)\}", html)
    assert narrow is not None
    assert ".app-company__three { grid-template-columns: repeat(2, minmax(0, 1fr));" in narrow[1]
    narrower = re.search(r"@container \(width < 460px\) \{([^}]*)\}", html)
    assert narrower is not None
    assert ".app-company__two, .app-company__three" in narrower[1]
    assert "grid-template-columns: minmax(0, 1fr);" in narrower[1]
