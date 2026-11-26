"""The drawer's form A (the company page's design, 11), as the founder changed it on 2026-11-26:
under its bar the head, the logo and the ticker, then the name, the ticker and the name each a
link to the company page, with no phase badge, no moat stamp and no chip of whose class it is,
which the screen's row and the company page show; one
caption, the sector and the industry; the company's brief in body text, cut to six lines by the
page's style; the value band, the meter and three levels in the screen's words, the fair value,
the buy level and the trim level, with no row for the fair band, which the meter names, or a
refused row's sentence where the meter draws no band; the price chart in its compact form; the figures,
P/E and Forward P/E as the screen's columns give them and the company page's Trading rows, with
the day of their data; then Company page, a link to the company page, and Request research,
which stand at the drawer's bottom edge while the rest scrolls. Nothing else: the route's lines,
the stance, the report's Summary and Details have left it. The mechanical value carries the hover of spec
2026-11-19 7.5, its warnings and the open company's note: on a row with no review the meter's fair
value and the Fair value row's figure, which the warnings mark leads where the row is marked; on a
reviewed row the meter's caption, with no mark; on a refused row nothing. The page's own script
runs in node after the bundle (``support.page``), and the tests read the tree ``sections`` returns
for ``page_answers``' LFOX and variants of it."""

import json
import re
from typing import Any

import pytest
from support import page_answers as answers
from support.page import NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# The drawer's levels: the company page's four less the Fair band, whose two ends the meter
# over the rows names (the founder, 2026-11-26).
LEVELS = ["Fair value", "Buy level", "Trim level"]
SECONDARY: dict[str, Any] = {
    "id": 4,
    "form": "parts",
    "valuePerShare": 150.0,
    "levels": {"buy": 112.5, "fairLow": 135.0, "fairHigh": 165.0, "trim": 225.0},
    "priceToValue": 1.216,
    "designation": "above",
}
# The open company's note and the hover's example, as the Words table gives them.
OPEN_NOTE = (
    "Preliminary estimate only. To ask an agent for a reviewed valuation, click Request research."
)
THREE = ["heavy capital spending", "negative free cash flow", "new shares issued"]
HOVER = (
    "3 warnings: heavy capital spending; negative free cash flow; new shares issued. " + OPEN_NOTE
)
# The warnings mark the page hands the bundle, undrawn: its props as given.
MARK: dict[str, Any] = {"props": {"words": THREE, "children": []}}
# The scripts whose chart and Trading rows the drawer draws once the company page's Overview
# answer has landed; without that answer the drawer draws from app.js alone.
SCRIPTS = (STATIC / "company.js", STATIC / "company_overview.js", STATIC / "company_chart.js")
# The detail with the multiples the screen's P/E columns read.
MULTIPLES = {"pe_reported": 14.143, "pe_forward": 19.4289, "pe_clean": 14.143}


def _drawn(detail: dict[str, Any], page: dict[str, Any] | None = None) -> Any:
    """What ``sections`` draws for ``detail``: the drawer's parts under its bar, with ``page``,
    the company page's Overview answer, where it has landed."""
    if page is None:
        return node("sections", [detail])
    return node("sections", [detail, page], *SCRIPTS)


def _with_multiples(multiples: dict[str, Any] | None) -> dict[str, Any]:
    """LFOX with ``multiples`` among its result's intermediates, or with none."""
    found = answers.detail()
    if multiples is None:
        found["result"]["intermediates"].pop("multiples", None)
    else:
        found["result"]["intermediates"]["multiples"] = multiples
    return found


def _facts(tree: Any) -> dict[str, list[tuple[str, str]]]:
    """The drawer's groups of figures by their titles, each its rows' names and figures."""
    part = _one(tree, "app-drawer__facts")
    found = {}
    for group in classed(part, "app-drawer__group"):
        [title] = classed(group, "app-drawer__grouptitle")
        [rows] = classed(group, "app-facts")
        names = [text(e) for e in elements(rows) if e.get("type") == "dt"]
        figures = [e for e in elements(rows) if e.get("type") == "dd"]
        assert {e["props"]["className"] for e in figures} == {"figure-sm"}
        found[text(title)] = list(zip(names, [text(e) for e in figures], strict=True))
    return found


def _one(tree: Any, name: str) -> dict[str, Any]:
    [found] = classed(tree, name)
    return found


def _meters(tree: Any) -> list[dict[str, Any]]:
    """The bundle's BandMeter elements, undrawn: their props as given."""
    return [e for e in elements(tree) if "fairValue" in e["props"]]


def _levels(tree: Any) -> list[tuple[str, str]]:
    """The names and the figures of the drawer's level rows."""
    [pairs] = classed(tree, "app-pairs")
    names = [text(e) for e in elements(pairs) if e.get("type") == "dt"]
    figures = [e for e in elements(pairs) if e.get("type") == "dd"]
    assert {e["props"]["className"] for e in figures} == {"figure-sm"}
    return list(zip(names, [text(e) for e in figures], strict=True))


def _buttons(tree: Any) -> list[dict[str, Any]]:
    """The buttons of the drawer's last part, undrawn: their props as given."""
    actions = _one(tree, "app-drawer__actions")
    return [
        e for e in elements(actions) if "variant" in e["props"] or "aria-expanded" in e["props"]
    ]


def _rule(selector: str) -> str:
    """The declarations of the page's one rule whose line opens with ``selector``, on one line."""
    css = _static_file("index.html")
    ends = [m.end() for m in re.finditer(r"(?m)^[ \t]*" + re.escape(selector), css)]
    assert len(ends) == 1, selector
    return " ".join(css[ends[0] : css.index("}", ends[0])].split())


CURRENCY = "Reports in TWD; an ADR: every per-share figure is per ADS; valued at TWD 32.40 per USD"
ONE_LINE = ("overflow: hidden;", "text-overflow: ellipsis;", "white-space: nowrap;")


def _names(tree: Any) -> list[str]:
    """The drawer's parts by their own class, in order."""
    return [part["props"]["className"].split()[-1] for part in tree if part is not None]


def _kids(element: dict[str, Any]) -> list[dict[str, Any]]:
    return [kid for kid in element["props"]["children"] if kid is not None]


def test_the_parts_in_order() -> None:
    """The head, the caption of the sector and the industry, the brief, the value band, the line
    that says what the figures are in, the price chart, the figures, then the buttons. The head
    is two rows: the logo and the ticker; the name."""
    tree = _drawn(answers.DETAIL, answers.OVERVIEW)
    assert isinstance(tree, list)
    assert _names(tree) == [
        "app-drawer__head",
        "app-drawer__sector",
        "app-drawer__brief",
        "app-drawer__band",
        "app-drawer__currency",
        "app-drawer__chart",
        "app-drawer__facts",
        "app-drawer__actions",
    ]
    head = tree[0]
    assert head["type"] == "header"
    first, name = _kids(head)
    assert (first["type"], first["props"]["className"]) == ("div", "app-drawer__id")
    logo, ticker = _kids(first)
    assert (logo["type"], logo["props"]["src"]) == ("img", answers.DETAIL["logo"])
    assert (ticker["type"], text(ticker)) == ("h2", answers.SYMBOL)
    assert (name["type"], text(name)) == ("p", "Lanternfield Optics Ltd")
    assert name["props"]["className"] == "body app-drawer__name"
    assert name["props"]["title"] == "Lanternfield Optics Ltd"


def test_every_part_over_the_band_keeps_its_room() -> None:
    """The founder, 2026-11-24: the value band and its meter stand at the same place whatever the
    company. So each part over the band is drawn for every company and has one height: the head's
    first row the logo's, with or without a logo; the name one line; the caption one line; the
    brief six. A company with no name, no sector or no brief has the part, empty, in its room."""
    assert _rule(".app-drawer__head {") == (
        "display: flex; flex-direction: column; gap: var(--space-2);"
    )
    assert _rule(".app-drawer__id {") == (
        "display: flex; align-items: center; gap: var(--space-2); min-width: 0; height: 24px;"
    )
    assert "width: 24px; height: 24px;" in _rule(".app-logo {")  # the row's height is the logo's
    assert "app-drawer__moat" not in _static_file("index.html")
    name = _rule(".app-drawer__name {")
    sector = _rule(".app-drawer__sector {")
    for rule in (name, sector):
        for declaration in ONE_LINE:
            assert declaration in rule, (rule, declaration)
    assert "min-height: 1lh;" in name and "min-height: 1lh;" in sector
    assert "min-height: 6lh;" in _rule(".app-drawer__brief {")
    bare = answers.detail(company=None, brief=None, logo=None, phase=None)
    tree = _drawn(bare)
    assert _names(tree)[:4] == [
        "app-drawer__head",
        "app-drawer__sector",
        "app-drawer__brief",
        "app-drawer__band",
    ]
    first, name_part = _kids(tree[0])
    assert [kid["type"] for kid in _kids(first)] == ["h2"]
    for part in (name_part, tree[1], tree[2]):
        assert part["type"] == "p"
        assert text(part) == ""
        assert part["props"].get("title") is None


def test_the_line_on_what_the_figures_are_in_stands_under_the_band() -> None:
    """Spec 2026-11-10 7.4, moved by the founder's word of 2026-11-24: the line on the reporting
    currency, the ADS and the rate takes one line or two, so it stands under the band, where its
    length moves no part over it, on a valued row and on a refused one. A company in USD that is
    no ADR has none."""
    for detail in (answers.DETAIL, answers.refused_detail()):
        tree = _drawn(detail)
        assert _names(tree)[-4:] == [
            "app-drawer__band",
            "app-drawer__currency",
            "app-drawer__facts",
            "app-drawer__actions",
        ]
        line = _one(tree, "app-drawer__currency")
        assert line["type"] == "p"
        assert line["props"]["className"] == "caption app-muted app-drawer__currency"
        assert line["props"]["children"] == [CURRENCY]
        assert classed(tree[0], "app-drawer__currency") == []  # not in the head
    assert _rule(".app-drawer__currency {") == "margin: var(--space-3) 0 0;"
    domestic = answers.detail(currency="USD", isAdr=False, adrRatio=None, fxRate=None)
    tree = _drawn(domestic)
    assert classed(tree, "app-drawer__currency") == []
    assert _names(tree)[-3:] == ["app-drawer__band", "app-drawer__facts", "app-drawer__actions"]


def test_the_caption_is_the_sector_and_the_industry() -> None:
    """Joined by a middle dot, as the screen names them; the parts the company has, on one line
    with the whole of it as the hover; empty with neither. The brief is not in it."""
    sector = _one(_drawn(answers.DETAIL), "app-drawer__sector")
    assert sector["type"] == "p"
    assert sector["props"]["className"] == "caption app-muted app-drawer__sector"
    assert text(sector) == "Technology · Semiconductors"
    assert sector["props"]["title"] == "Technology · Semiconductors"
    company = answers.DETAIL["company"]
    energy = answers.detail(company=company | {"sector": "Energy", "industry": None})
    assert text(_one(_drawn(energy), "app-drawer__sector")) == "Energy"
    for unnamed in (company | {"sector": None, "industry": None}, None):
        empty = _one(_drawn(answers.detail(company=unnamed)), "app-drawer__sector")
        assert text(empty) == "" and empty["props"].get("title") is None


def test_the_brief_is_whole_and_takes_six_lines_by_the_style() -> None:
    """The whole stored brief, in body text; the style cuts it at six lines with an ellipsis and
    keeps six lines' room for a shorter one (the founder, 2026-11-24), so the value band under it
    does not move with the brief's length. A company with no stored brief has the room, empty."""
    brief = _one(_drawn(answers.DETAIL), "app-drawer__brief")
    assert brief["type"] == "p"
    assert brief["props"]["className"] == "body app-drawer__brief"
    assert text(brief) == answers.DETAIL["brief"]
    assert text(_one(_drawn(answers.detail(brief=None)), "app-drawer__brief")) == ""
    rule = _rule(".app-drawer__brief {")
    for declaration in (
        "display: -webkit-box;",
        "-webkit-box-orient: vertical;",
        "-webkit-line-clamp: 6;",
        "line-clamp: 6;",
        "min-height: 6lh;",
        "overflow: hidden;",
        "color: var(--ink-muted);",
    ):
        assert declaration in rule, declaration


def test_the_levels_use_the_screen_s_words() -> None:
    """Under the meter, as the meter draws it, three levels in the screen's words, each a
    figure: the fair value, the buy level and the trim level. The fair band has no row (the
    founder, 2026-11-26): the meter over the rows names its two ends. The company page's value
    block keeps the four (``levelRows``). No margin of safety, no multiple of the value and no
    caption of the moat."""
    tree = _drawn(answers.DETAIL)
    band = _one(tree, "app-drawer__band")
    [meter] = _meters(band)
    assert meter == node("meter", [answers.DETAIL])
    assert _levels(band) == [
        ("Fair value", "$196.50"),
        ("Buy level", "$147.38"),
        ("Trim level", "$294.75"),
    ]
    assert (meter["props"]["low"], meter["props"]["high"]) == (176.85, 216.15)  # the band's ends
    assert "Fair band" not in json.dumps(tree, ensure_ascii=False)
    four = node("levelRows", [answers.DETAIL])
    assert [name for name, _ in four] == ["Fair value", "Buy level", "Fair band", "Trim level"]
    found = list(elements(band))
    assert found.index(meter) < found.index(_one(band, "app-pairs"))
    said = json.dumps(tree, ensure_ascii=False)
    for gone in ("Margin of safety", "× value", "moat's", "margin for no moat", "value less the"):
        assert gone not in said, gone


def _links(head: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in elements(head) if e.get("type") == "a"]


def test_the_ticker_and_the_name_link_to_the_company_page() -> None:
    """The founder, 2026-11-26: in the drawer's head the ticker and the company's name are each
    a link to the company's page, at the address the table's ticker links to and the Company
    page button opens, the symbol encoded as there; the name's is out of the Tab order, as the
    table's is, the ticker's link before it being the keyboard's stop. A company with no name
    has the ticker's link alone, its name's line empty. Each reads as the text it is, an
    underline on hover and the focus ring on focus, as the table's links do."""
    for symbol, href in (("BRK.B", "#company/BRK.B"), ("BRK/B", "#company/BRK%2FB")):
        detail = answers.detail()
        detail["result"]["symbol"] = symbol
        [head, *_] = _drawn(detail)
        first, name = _kids(head)
        ticker = _kids(first)[-1]
        assert ticker["type"] == "h2"
        assert _kids(ticker) == [
            {
                "type": "a",
                "props": {"className": "app-drawer__link", "href": href, "children": [symbol]},
            }
        ]
        assert _kids(name) == [
            {
                "type": "a",
                "props": {
                    "className": "app-drawer__link",
                    "href": href,
                    "tabIndex": -1,
                    "children": ["Lanternfield Optics Ltd"],
                },
            }
        ]
        assert [link["props"]["href"] for link in _links(head)] == [href, href]
        page, _ = _buttons(_drawn(detail))
        assert page["props"]["href"] == href
    [head, *_] = _drawn(answers.detail(company=None))
    assert [text(link) for link in _links(head)] == [answers.SYMBOL]
    assert "companyHref({ ticker: r.symbol })" in _static_file("app.js")
    for state in ("", ":hover", ":focus-visible"):  # the look of the table's links
        assert _rule(f".app-drawer__link{state} {{") == _rule(f".fb-screen__company{state} {{")
    assert _rule(".app-drawer__link {") == "color: inherit; text-decoration: none;"


def test_the_company_page_button_s_address() -> None:
    """Company page, first and primary, a link to the company's page, its symbol encoded as the
    page's other links to a company encode it; then Request research as before."""
    for symbol, href in (("BRK.B", "#company/BRK.B"), ("BRK/B", "#company/BRK%2FB")):
        detail = answers.detail()
        detail["result"]["symbol"] = symbol
        page, research = _buttons(_drawn(detail))
        assert page["props"] == {
            "variant": "primary",
            "href": href,
            "children": ["Company page"],
        }
        assert research["props"]["children"] == ["Request research"]
        assert research["props"]["disabled"] is False
    rule = _rule(".app-drawer__actions {")
    for declaration in ("display: flex;", "flex-wrap: wrap;", "gap: var(--space-2);"):
        assert declaration in rule, declaration


def test_request_research_s_box_stands_from_the_row_of_buttons() -> None:
    """Request research's box stands from the right edge of the row of buttons, not from its own
    button (the watchlist page's design, 10). The two buttons fill the row, so when the drawer
    scrolls, its scrollbar wraps them and Request research drops to the row's left. A box from
    that button's right edge would then stand past the drawer's left edge, which clips it. The
    row stands at the drawer's bottom edge (the founder, 2026-11-26), so the box opens over the
    row, not under it, a little inside the row's right edge. The two buttons share the row at
    any width of the body, a scrollbar's width less too: each takes its share, its words
    centred."""
    assert "position: sticky;" in _rule(".app-drawer__actions {")
    assert _rule(".app-drawer__actions .app-request {") == "position: static;"
    assert "left: auto; right: 0;" in _rule(".app-request .fb-menu {")
    assert _rule(".app-drawer__actions .app-request .fb-menu {") == (
        "top: auto; bottom: calc(100% + var(--space-1)); right: var(--space-2);"
    )
    shared = _rule(".app-drawer__actions > .fb-btn, .app-drawer__actions > .app-request {")
    assert shared == "flex: 1 1 auto;"
    assert _rule(".app-drawer__actions .fb-btn {") == (
        "justify-content: center; padding-inline: var(--space-2);"
    )
    assert _rule(".app-drawer__actions .app-request > .fb-btn {") == "width: 100%;"


def test_request_research_keeps_its_open_item_s_line() -> None:
    """An open item disables the button and draws its line under the two buttons."""
    item = {"id": 12, "state": "pending", "mode": "full report", "claimedBy": None, "launch": None}
    tree = _drawn(answers.detail(item=item))
    _, research = _buttons(tree)
    assert research["props"]["disabled"] is True
    line = _one(_one(tree, "app-drawer__actions"), "app-requested")
    assert text(line) == "Requested · pending"


def _young_growth() -> dict[str, Any]:
    """LFOX valued on the revenue growth route as a Young Growth company, with the figures the
    drawer once wrote under its band: the failure probability, the cross-check and the required
    return every year is discounted at."""
    detail = answers.detail(phase="Young Growth")
    result = detail["result"]
    result["route"] = "revenue-growth"
    result["phase"]["phase"] = "Young Growth"
    result["inputs"] = [{"name": "required_return", "tag": "RULE", "value": 0.09}]
    result["intermediates"] |= {
        "failure_probability": {"value": None, "reason": "no survival table fits"},
        "growth_route": {"value_per_share": 150.0, "implied_growth": 0.12},
        "implied_margin": 0.31,
    }
    return detail


def _start_up() -> dict[str, Any]:
    """LFOX refused as a Start-up company, with the figures its route writes."""
    detail = answers.refused_detail() | {"phase": "Start-up"}
    result = detail["result"]
    result["phase"]["phase"] = "Start-up"
    result["refusal"] = "a Start-up company has no value until it earns"
    result["intermediates"] |= {
        "requirement": {"reason": "no peers", "revenue_0": 1e9},
        "implied_margin": 0.42,
        "e_trailing": 1.2,
        "growth_route": {"value_per_share": 40.0, "implied_growth": 0.2},
    }
    return detail


def test_what_left_the_drawer_is_not_drawn() -> None:
    """No route's name under the levels, no cross-check, no line of a Young Growth or a Start-up
    row, no margin the price needs under a refusal; no stance, no Summary and no Open the report
    on a company with a report; no Details and nothing it listed."""
    reviewed = answers.reviewed_detail()
    for detail in (answers.DETAIL, _young_growth(), _start_up(), reviewed):
        tree = _drawn(detail)
        said = json.dumps(tree, ensure_ascii=False)
        for gone in (
            "route",
            "cross-check",
            "Failure probability",
            "tier 1",
            "Discounted at",
            "price needs",
            "Open the report",
            "Details",
            "Phase evidence",
            "Inputs",
            "Intermediate results",
            "Flags",
            "Policy ",
            "Add a note",
            "MOAT",
            reviewed["report"]["summary"]["parts"][0],
        ):
            assert gone not in said, (detail["result"]["phase"]["phase"], gone)
        for name in ("app-stance", "fb-stance", "app-disclosure", "app-section", "app-levels"):
            assert classed(tree, name) == [], name
        for name in ("app-moat", "app-drawer__moat", "fb-chip"):  # the founder, 2026-11-26
            assert classed(tree, name) == [], name
        assert [e for e in elements(tree) if "phase" in e["props"]] == []  # no PhaseBadge
        assert [e for e in elements(tree) if "principal" in e["props"]] == []  # no chip
        assert [e for e in elements(tree) if "sections" in e["props"]] == []  # no ReportReader
        assert [e for e in elements(tree) if "asOf" in e["props"]] == []  # no ValidityWindow


def test_a_refused_row_draws_its_refusal() -> None:
    """In the band's place the refusal's sentence; no meter and no levels."""
    tree = _drawn(answers.refused_detail())
    band = _one(tree, "app-drawer__band")
    refusal = _one(band, "app-refusal")
    assert (refusal["type"], refusal["props"]["className"]) == ("p", "body app-refusal")
    assert text(refusal) == answers.REFUSAL
    assert _meters(tree) == []
    assert classed(tree, "app-pairs") == []
    assert _names(tree)[-4:] == [
        "app-drawer__band",
        "app-drawer__currency",
        "app-drawer__facts",
        "app-drawer__actions",
    ]


@pytest.mark.parametrize(
    ("changes", "value", "band"),
    [
        ({"review": answers.REVIEW}, 182.0, (163.8, 200.2)),
        ({"secondary": SECONDARY}, 150.0, (135.0, 165.0)),
    ],
    ids=["review", "secondary"],
)
def test_a_refused_row_with_a_band_draws_the_band_and_no_sentence(
    changes: dict[str, Any], value: float, band: tuple[float, float]
) -> None:
    """A refused row whose review or secondary valuation gives a band draws that band and its
    levels, as the meter draws it, and no refusal sentence."""
    detail = answers.refused_detail() | changes
    tree = _drawn(detail)
    [meter] = _meters(tree)
    assert meter == node("meter", [detail])
    assert meter["props"]["fairValue"] == value
    assert [name for name, _ in _levels(tree)] == LEVELS
    assert (meter["props"]["low"], meter["props"]["high"]) == band
    assert classed(tree, "app-refusal") == []


def test_a_reviewed_row_draws_the_review_s_band() -> None:
    """The review counts: the meter and the levels are the review's."""
    detail = answers.reviewed_detail()
    tree = _drawn(detail)
    [meter] = _meters(tree)
    assert meter == node("meter", [detail])
    assert meter["props"]["fairValue"] == 182.0
    assert _levels(tree) == [
        ("Fair value", "$182.00"),
        ("Buy level", "$145.60"),
        ("Trim level", "$273.00"),
    ]


def test_the_head_is_the_logo_the_ticker_and_the_name() -> None:
    """The founder, 2026-11-26: the drawer's head draws no phase badge, no moat stamp and no chip
    of whose class it is, whatever the company's phase and class and whoever set the class: the
    screen's row shows the phase and the class, and the company page all three."""
    details = [answers.detail(moat=moat) for moat in ("Wide", "Narrow", "None")]
    details += [answers.reviewed_detail(), answers.unset_detail()]
    details += [answers.detail(phase="Mature Stable"), answers.detail(phase=None)]
    for detail in details:
        [head, *_] = _drawn(detail)
        first, name = _kids(head)
        assert [kid["type"] for kid in _kids(first)] == ["img", "h2"]
        assert name["props"]["className"] == "body app-drawer__name"
        assert len(_links(head)) == 2  # the ticker and the name, to the company page
        said = json.dumps(head, ensure_ascii=False)
        for gone in ("MOAT", "phase", "principal", "app-moat"):
            assert gone not in said, gone


def test_the_chart_is_the_company_page_s_in_its_compact_form() -> None:
    """Under the band, once the company page's Overview answer has landed: the price chart on
    the answer's prices, compact, keyed on the company so each company's opens at 1Y with no day
    picked. Before the answer lands, and where its read failed, the drawer draws no chart."""
    tree = _drawn(answers.DETAIL, answers.OVERVIEW)
    part = _one(tree, "app-drawer__chart")
    assert part["type"] == "section"
    [chart] = _kids(part)
    assert chart["props"] == {
        "key": answers.SYMBOL,
        "prices": answers.OVERVIEW["prices"],
        "compact": True,
        "children": [],
    }
    assert (
        "h(page.companyChart.Chart, { key: r.symbol, prices: answer.prices, compact: true })"
        in (_static_file("app.js"))
    )
    for none in (None, {}):
        assert classed(node("sections", [answers.DETAIL, none]), "app-drawer__chart") == []
    refused = _drawn(answers.refused_detail(), answers.OVERVIEW)
    assert len(classed(refused, "app-drawer__chart")) == 1  # a refused company has prices too
    rule = _rule(".app-drawer__chart, .app-drawer__facts {")
    assert rule == (
        "margin-top: var(--space-4); padding-top: var(--space-4);"
        " border-top: 1px solid var(--hairline);"
    )


def test_the_figures_are_the_screen_s_multiples_and_the_page_s_trading_rows() -> None:
    """Under the chart, two groups in the company page's words. Valuation: P/E and Forward P/E,
    the multiples of the company's result as the screen's columns write them, to one decimal with
    an x, a dash without one. Trading: the rows of the company page's Price facts, from the same
    function, so the two views never differ. Under them the day of the answer's data, in the
    company page's words. No chip, no cite and no vendor's name."""
    tree = _drawn(_with_multiples(MULTIPLES), answers.OVERVIEW)
    assert _facts(tree) == {
        "Valuation": [("P/E", "14.1x"), ("Forward P/E", "19.4x")],
        "Trading": [
            tuple(row)
            for row in node("companyPage.tradingRows", [answers.OVERVIEW["trading"]], *SCRIPTS)
        ],
    }
    assert [name for name, _ in _facts(tree)["Trading"]] == [
        "Open",
        "Previous close",
        "Day range",
        "52 weeks",
        "50-day average",
        "200-day average",
        "Volume",
        "Average volume",
        "Next earnings",
    ]
    part = _one(tree, "app-drawer__facts")
    assert part["type"] == "section"
    asof = _one(part, "app-drawer__asof")
    assert asof["props"]["className"] == "caption app-muted app-drawer__asof"
    assert text(asof) == "data 14 Nov 2026"
    assert [e for e in elements(part) if "basis" in e["props"] or "principal" in e["props"]] == []
    for multiples, figures in (
        (None, ["—", "—"]),
        ({"pe_reported": None, "pe_forward": 31.25}, ["—", "31.3x"]),
        ({"pe_reported": -12.34, "pe_forward": None}, ["−12.3x", "—"]),
    ):
        valuation = _facts(_drawn(_with_multiples(multiples)))["Valuation"]
        assert valuation == list(zip(["P/E", "Forward P/E"], figures, strict=True))


def test_the_figures_before_the_page_s_answer_lands() -> None:
    """The multiples are the detail's own, so the Valuation group draws with the detail; the
    Trading rows and the day of their data wait for the company page's Overview answer, and stay
    away where its read failed. A refused company has the part too."""
    for detail in (_with_multiples(MULTIPLES), answers.refused_detail()):
        tree = _drawn(detail)
        assert list(_facts(tree)) == ["Valuation"]
        assert classed(tree, "app-drawer__asof") == []
    undated = _drawn(answers.DETAIL, answers.OVERVIEW | {"dataDate": None})
    assert list(_facts(undated)) == ["Valuation", "Trading"]
    assert classed(undated, "app-drawer__asof") == []


def test_the_figures_rows_are_a_name_and_a_figure_at_the_right() -> None:
    """Each group: its title in label, upper case and faint, then its rows, the name in caption
    at the left and the figure in figure-sm at the right edge, so a column of figures ends on
    one line."""
    assert _rule(".app-drawer__grouptitle {") == (
        "margin: 0 0 var(--space-1); color: var(--ink-faint); text-transform: uppercase;"
    )
    assert _rule(".app-drawer__group + .app-drawer__group {") == "margin-top: var(--space-3);"
    rows = _rule(".app-facts {")
    assert "display: grid; grid-template-columns: minmax(0, 1fr) max-content;" in rows
    assert _rule(".app-facts dt {") == "color: var(--ink-muted);"
    assert _rule(".app-facts dd {") == "margin: 0; text-align: right; white-space: nowrap;"
    assert _rule(".app-drawer__asof {") == "margin: var(--space-2) 0 0;"
    tree = _drawn(_with_multiples(MULTIPLES), answers.OVERVIEW)
    for title in classed(tree, "app-drawer__grouptitle"):
        assert (title["type"], title["props"]["className"]) == (
            "h3",
            "label app-drawer__grouptitle",
        )
    for rows_ in classed(tree, "app-facts"):
        assert rows_["type"] == "dl"
        assert {e["props"]["className"] for e in elements(rows_) if e.get("type") == "dt"} == {
            "caption"
        }


def test_the_buttons_stand_at_the_drawer_s_bottom_edge() -> None:
    """The founder, 2026-11-26: with the chart and the figures the drawer's parts are longer
    than most windows, so the buttons, the last of the parts, leave the body and stand at the
    drawer's bottom edge on its raised surface, over a hairline, while the body scrolls; where
    the parts are shorter than the drawer the body takes the room left, so the buttons stand at
    the bottom edge for every company. While the drawer turns to another company the buttons
    fade as the body does, the row's surface staying whole."""
    shown = {
        "symbol": answers.SYMBOL,
        "body": answers.DETAIL,
        "page": None,
        "loading": False,
        "error": None,
    }
    for drawer, loading in ((shown, False), (shown | {"loading": True}, True)):
        tree = node("drawer", [drawer])
        bar, body, foot = _kids(tree)
        assert bar["props"]["className"] == "app-drawer__bar"
        assert body["props"]["className"] == (
            "app-drawer__body is-loading" if loading else "app-drawer__body"
        )
        assert foot["props"]["className"] == (
            "app-drawer__actions is-loading" if loading else "app-drawer__actions"
        )
        assert classed(body, "app-drawer__actions") == []
        [parts] = body["props"]["children"]
        assert _names(parts)[-1] == "app-drawer__facts"
        assert [text(button) for button in _buttons([foot])] == ["Company page", "Request research"]
    failed = node("drawer", [shown | {"body": None, "error": "did not load"}])
    assert [kid["props"]["className"] for kid in _kids(failed)] == [
        "app-drawer__bar",
        "app-drawer__body",
    ]
    drawer = _rule(".app-drawer {")
    assert "overflow-y: auto;" in drawer and "display: flex; flex-direction: column;" in drawer
    assert "flex: 1 0 auto;" in _rule(".app-drawer__body {")
    foot_rule = _rule(".app-drawer__actions {")
    for declaration in (
        "position: sticky;",
        "bottom: 0;",
        "background: var(--surface-raised);",
        "border-top: 1px solid var(--hairline);",
        "padding: var(--space-3) var(--space-4);",
    ):
        assert declaration in foot_rule, declaration
    assert _rule(".app-drawer__actions.is-loading > * {") == "opacity: 0.5;"


def _fair_figure(tree: Any) -> Any:
    """The figure of the drawer's Fair value row: the one child of its first ``dd``."""
    [pairs] = classed(tree, "app-pairs")
    first = next(e for e in elements(pairs) if e.get("type") == "dd")
    [figure] = first["props"]["children"]
    return figure


def _marks(tree: Any) -> list[dict[str, Any]]:
    """The warnings marks the page hands the bundle, undrawn: the elements given ``words``."""
    return [e for e in elements(tree) if "words" in e["props"]]


def test_an_unreviewed_value_carries_the_hover_and_the_mark() -> None:
    """A valued row with no review and three warnings, which the server marks: the meter's fair
    value has the hover as its title, the warnings' count and words, then the open company's
    note; the Fair value row's figure is the value in a span with the same title, the warnings
    mark before it. A review that counts with no value of its own leaves the same: the mechanical
    value is still the meter's. The mark, drawn, is the screen's bullet, named by the hover's
    first sentence; the meter, drawn, titles its fair value's marker."""
    unreviewed = answers.detail(warnings=THREE, marked=True)
    refusing = unreviewed | {"review": answers.REVIEW | {"value": None, "levels": None}}
    for detail in (unreviewed, refusing):
        tree = _drawn(detail)
        [meter] = _meters(tree)
        assert meter == node("meter", [detail])
        assert meter["props"]["fairTitle"] == HOVER
        assert "captionTitle" not in meter["props"]
        assert _fair_figure(tree) == {
            "type": "span",
            "props": {"title": HOVER, "children": [MARK, "$196.50"]},
        }
        assert _marks(tree) == [MARK]
        assert _levels(tree)[0] == ("Fair value", "$196.50")
    assert node("Fairband.WarningMark", [MARK["props"]]) == {
        "type": "span",
        "props": {
            "className": "fb-warnmark",
            "role": "img",
            "aria-label": "3 warnings: heavy capital spending; negative free cash flow; new shares"
            " issued.",
            "children": ["•"],
        },
    }
    [meter] = _meters(_drawn(unreviewed))
    [fair] = classed(node("Fairband.BandMeter", [meter["props"]]), "fb-band__fairmark")
    assert fair["props"]["title"] == HOVER


def test_a_row_under_the_cut_off_has_the_hover_and_no_mark() -> None:
    """A valued row the server does not mark keeps the hover and draws no mark: two warnings
    under the cut-off, one, none (the note alone), and a detail without the two fields, which
    reads as none."""
    bare = {k: v for k, v in answers.detail().items() if k not in ("warnings", "marked")}
    cases = [
        (
            answers.detail(warnings=THREE[:2]),
            "2 warnings: heavy capital spending; negative free cash flow. " + OPEN_NOTE,
        ),
        (answers.detail(warnings=["one-time items"]), "1 warning: one-time items. " + OPEN_NOTE),
        (answers.DETAIL, OPEN_NOTE),
        (bare, OPEN_NOTE),
    ]
    for detail, hover in cases:
        tree = _drawn(detail)
        [meter] = _meters(tree)
        assert meter["props"]["fairTitle"] == hover
        assert _fair_figure(tree) == {
            "type": "span",
            "props": {"title": hover, "children": [None, "$196.50"]},
        }
        assert _marks(tree) == []


def test_a_reviewed_row_s_caption_carries_the_hover_and_no_mark() -> None:
    """The review counts: the mechanical value is the meter's caption, "mechanical $196.50",
    whose title is the hover with the snapshot's warnings; the meter's fair value is the review's
    and has no title, the Fair value row's figure is the review's text, and no mark stands, even
    on a detail that came marked."""
    for marked in (False, True):
        detail = answers.reviewed_detail() | {"warnings": THREE, "marked": marked}
        tree = _drawn(detail)
        [meter] = _meters(tree)
        assert meter["props"]["caption"] == "mechanical $196.50"
        assert meter["props"]["captionTitle"] == HOVER
        assert "fairTitle" not in meter["props"]
        assert _fair_figure(tree) == "$182.00"
        assert _marks(tree) == []


def test_a_refused_row_carries_no_hover() -> None:
    """A refused row keeps its warnings' words but has no mechanical value: its sentence has no
    title, the review's or the secondary valuation's band it draws in its place has none, its Fair
    value row is that band's text, and no mark stands, even on a detail that came marked."""
    refused = answers.refused_detail() | {"warnings": THREE, "marked": True}
    assert _one(_drawn(refused), "app-refusal")["props"].get("title") is None
    for detail, figure in (
        (refused, None),
        (refused | {"review": answers.REVIEW}, "$182.00"),
        (refused | {"secondary": SECONDARY}, "$150.00"),
    ):
        tree = _drawn(detail)
        assert "Preliminary estimate only" not in json.dumps(tree, ensure_ascii=False)
        for meter in _meters(tree):
            assert "fairTitle" not in meter["props"] and "captionTitle" not in meter["props"]
        assert _marks(tree) == []
        if figure is not None:
            assert _fair_figure(tree) == figure
