"""The drawer's form A (the company page's design, 11): under its bar the head as before, the moat
stamp after the phase badge, and the chip of the owner's or an agent's class after it (spec
2026-11-19 8.8); one caption, the sector and the industry; the company's brief in body
text, cut to six lines by the page's style; the value band, the meter and the four levels in the
screen's words, or a refused row's sentence where the meter draws no band; then Company page, a
link to the company page, and Request research. Nothing else: the route's lines, the stance, the
report's Summary and Details have left it. The mechanical value carries the hover of spec
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
from support.page import NODE, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

LEVELS = ["Fair value", "Buy level", "Fair band", "Trim level"]
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


def _drawn(detail: dict[str, Any]) -> Any:
    """What ``sections`` draws for ``detail``: the drawer's parts under its bar."""
    return node("sections", [detail])


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
    that says what the figures are in, then the buttons. The head is three rows: the logo, the
    ticker and the phase badge; the moat stamp; the name."""
    tree = _drawn(answers.DETAIL)
    assert isinstance(tree, list)
    assert _names(tree) == [
        "app-drawer__head",
        "app-drawer__sector",
        "app-drawer__brief",
        "app-drawer__band",
        "app-drawer__currency",
        "app-drawer__actions",
    ]
    head = tree[0]
    assert head["type"] == "header"
    first, second, name = _kids(head)
    assert (first["type"], first["props"]["className"]) == ("div", "app-drawer__id")
    logo, ticker, badge = _kids(first)
    assert (logo["type"], logo["props"]["src"]) == ("img", answers.DETAIL["logo"])
    assert (ticker["type"], text(ticker)) == ("h2", answers.SYMBOL)
    assert badge["props"] == {"phase": 4, "size": "sm", "children": []}
    assert (second["type"], second["props"]["className"]) == ("div", "app-drawer__moat")
    [stamp] = _kids(second)
    assert text(stamp) == "WIDE MOAT"
    assert name == {
        "type": "p",
        "props": {
            "className": "body app-drawer__name",
            "title": "Lanternfield Optics Ltd",
            "children": ["Lanternfield Optics Ltd"],
        },
    }


def test_every_part_over_the_band_keeps_its_room() -> None:
    """The founder, 2026-11-24: the value band and its meter stand at the same place whatever the
    company. So each part over the band is drawn for every company and has one height: the head's
    first row the logo's, with or without a logo or a badge; the moat's row the stamp's, with or
    without the chip, whose model gives way where the row is full; the name one line; the caption
    one line; the brief six. A company with no name, no sector or no brief has the part, empty,
    in its room."""
    assert _rule(".app-drawer__head {") == (
        "display: flex; flex-direction: column; gap: var(--space-2);"
    )
    rows = _rule(".app-drawer__id, .app-drawer__moat {")
    assert rows == "display: flex; align-items: center; gap: var(--space-2); min-width: 0;"
    assert _rule(".app-drawer__id {") == "height: 24px;"
    assert "width: 24px; height: 24px;" in _rule(".app-logo {")  # the row's height is the logo's
    assert _rule(".app-drawer__moat {") == "height: 18px;"
    assert _rule(".app-drawer__moat .fb-chip {") == "min-width: 0;"
    role = _rule(".app-drawer__moat .fb-chip__role {")
    name = _rule(".app-drawer__name {")
    sector = _rule(".app-drawer__sector {")
    for rule in (role, name, sector):
        for declaration in ONE_LINE:
            assert declaration in rule, (rule, declaration)
    assert "min-width: 0;" in role
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
    first, second, name_part = _kids(tree[0])
    assert [kid["type"] for kid in _kids(first)] == ["h2"]
    assert text(_one(second, "app-moat")) == "WIDE MOAT"
    for part in (name_part, tree[1], tree[2]):
        assert part["type"] == "p"
        assert text(part) == ""
        assert part["props"].get("title") is None


def test_the_line_on_what_the_figures_are_in_stands_under_the_band() -> None:
    """Spec 2026-11-10 7.4, moved by the founder's word of 2026-11-24: the line on the reporting
    currency, the ADS and the rate takes one line or two, so it stands under the band, where its
    length moves the buttons alone, on a valued row and on a refused one. A company in USD that
    is no ADR has none."""
    for detail in (answers.DETAIL, answers.refused_detail()):
        tree = _drawn(detail)
        assert _names(tree)[-3:] == [
            "app-drawer__band",
            "app-drawer__currency",
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
    assert _names(tree)[-2:] == ["app-drawer__band", "app-drawer__actions"]


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
    """Under the meter, as the meter draws it, the four levels in the screen's words, each a
    figure; no margin of safety, no multiple of the value and no caption of the moat."""
    tree = _drawn(answers.DETAIL)
    band = _one(tree, "app-drawer__band")
    [meter] = _meters(band)
    assert meter == node("meter", [answers.DETAIL])
    assert _levels(band) == [
        ("Fair value", "$196.50"),
        ("Buy level", "$147.38"),
        ("Fair band", "$176.85 – $216.15"),
        ("Trim level", "$294.75"),
    ]
    found = list(elements(band))
    assert found.index(meter) < found.index(_one(band, "app-pairs"))
    said = json.dumps(tree, ensure_ascii=False)
    for gone in ("Margin of safety", "× value", "moat's", "margin for no moat", "value less the"):
        assert gone not in said, gone


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
    """Request research's box stands from the right edge of the row of buttons, under the row,
    not from its own button (the watchlist page's design, 10). The two buttons fill the row, so
    when the drawer scrolls, its scrollbar wraps them and Request research drops to the row's
    left. A box from that button's right edge would then stand past the drawer's left edge,
    which clips it."""
    assert "position: relative;" in _rule(".app-drawer__actions {")
    assert _rule(".app-drawer__actions .app-request {") == "position: static;"
    assert "left: auto; right: 0;" in _rule(".app-request .fb-menu {")


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
            reviewed["report"]["summary"]["parts"][0],
        ):
            assert gone not in said, (detail["result"]["phase"]["phase"], gone)
        for name in ("app-stance", "fb-stance", "app-disclosure", "app-section", "app-levels"):
            assert classed(tree, name) == [], name
        assert [e for e in elements(tree) if "sections" in e["props"]] == []  # no ReportReader
        assert [e for e in elements(tree) if "asOf" in e["props"]] == []  # no ValidityWindow


def test_a_refused_row_draws_its_refusal() -> None:
    """In the band's place the refusal's sentence; no meter and no levels. The moat stamp stays:
    the class is the moat table's, a refused row's too."""
    tree = _drawn(answers.refused_detail())
    band = _one(tree, "app-drawer__band")
    refusal = _one(band, "app-refusal")
    assert (refusal["type"], refusal["props"]["className"]) == ("p", "body app-refusal")
    assert text(refusal) == answers.REFUSAL
    assert _meters(tree) == []
    assert classed(tree, "app-pairs") == []
    assert text(_one(tree, "app-moat")) == "WIDE MOAT"
    assert _names(tree)[-3:] == ["app-drawer__band", "app-drawer__currency", "app-drawer__actions"]


@pytest.mark.parametrize(
    ("changes", "value", "band"),
    [
        ({"review": answers.REVIEW}, 182.0, "$163.80 – $200.20"),
        ({"secondary": SECONDARY}, 150.0, "$135.00 – $165.00"),
    ],
    ids=["review", "secondary"],
)
def test_a_refused_row_with_a_band_draws_the_band_and_no_sentence(
    changes: dict[str, Any], value: float, band: str
) -> None:
    """A refused row whose review or secondary valuation gives a band draws that band and its
    levels, as the meter draws it, and no refusal sentence."""
    detail = answers.refused_detail() | changes
    tree = _drawn(detail)
    [meter] = _meters(tree)
    assert meter == node("meter", [detail])
    assert meter["props"]["fairValue"] == value
    assert [name for name, _ in _levels(tree)] == LEVELS
    assert dict(_levels(tree))["Fair band"] == band
    assert classed(tree, "app-refusal") == []


def test_a_reviewed_row_draws_the_review_s_band() -> None:
    """The review counts: the meter and the levels are the review's, and the stamp the class of
    the agent's row its moat override became."""
    detail = answers.reviewed_detail()
    tree = _drawn(detail)
    [meter] = _meters(tree)
    assert meter == node("meter", [detail])
    assert meter["props"]["fairValue"] == 182.0
    assert _levels(tree) == [
        ("Fair value", "$182.00"),
        ("Buy level", "$145.60"),
        ("Fair band", "$163.80 – $200.20"),
        ("Trim level", "$273.00"),
    ]
    assert text(_one(tree, "app-moat")) == "NARROW MOAT"


def _badges(head: dict[str, Any]) -> list[dict[str, Any]]:
    """The head's PhaseBadge elements, undrawn: their props as given."""
    return [e for e in elements(head["props"]["children"]) if "phase" in e["props"]]


def test_the_moat_stamp_follows_the_phase_badge() -> None:
    """The phase badge ends the head's first row and the moat stamp starts its second, in the
    stamp's words, the chip of an agent's class after it; a company with no row in the moat table
    is stamped ``MOAT NOT SET``, and a row with no phase has no badge."""
    for moat, words in (("Wide", "WIDE MOAT"), ("Narrow", "NARROW MOAT"), ("None", "NO MOAT")):
        [head, *_] = _drawn(answers.detail(moat=moat))
        first, second, _ = _kids(head)
        assert "phase" in _kids(first)[-1]["props"]
        [stamp] = _kids(second)
        assert stamp == node("moatStamp", [{"moat": moat}])
        assert text(stamp) == words
    agent = answers.reviewed_detail()
    [head, *_] = _drawn(agent)
    stamp, chip = _kids(_kids(head)[1])
    assert text(stamp) == "NARROW MOAT"
    assert chip == node("moatChip", [agent])
    [head, *_] = _drawn(answers.unset_detail())
    assert text(_one(head, "app-moat")) == "MOAT NOT SET"
    [head, *_] = _drawn(answers.detail(phase=None))
    assert _badges(head) == []
    assert text(_one(head, "app-moat")) == "WIDE MOAT"


def test_the_badge_draws_the_shown_phase() -> None:
    """Spec 2026-11-23 refresh experience, 4.4: the head's badge draws the detail's ``phase``, the
    phase the screen's row shows, a review's where the review has a value, not its result's, the
    classifier's: Mature Stable over a result of Mature Growth is badge 5; none is no badge."""
    assert answers.DETAIL["result"]["phase"]["phase"] == "Mature Growth"
    [head, *_] = _drawn(answers.detail(phase="Mature Stable"))
    [badge] = _badges(head)
    assert badge["props"] == {"phase": 5, "size": "sm", "children": []}
    [head, *_] = _drawn(answers.detail(phase=None))
    assert _badges(head) == []


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
