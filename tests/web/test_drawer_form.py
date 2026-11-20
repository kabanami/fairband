"""The drawer's form A (the company page's design, 11): under its bar the head as before, the moat
stamp after the phase badge; one caption, the sector and the industry; the company's brief in body
text, cut to six lines by the page's style; the value band, the meter and the four levels in the
screen's words, or a refused row's sentence where the meter draws no band; then Company page, a
link to the company page, and Request research. Nothing else: the route's lines, the stance, the
report's Summary and Details have left it. The page's own script runs in node after the bundle
(``support.page``), and the tests read the tree ``sections`` returns for ``page_answers``' LFOX
and variants of it."""

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


def test_the_parts_in_order() -> None:
    """The head, the caption of the sector and the industry, the brief, the value band, then the
    buttons; in the head the logo, the ticker, the phase badge, the moat stamp, the name and the
    line that says what the figures are in."""
    tree = _drawn(answers.DETAIL)
    assert isinstance(tree, list)
    parts = [part for part in tree if part is not None]
    names = ["app-drawer__head", "app-drawer__sector", "app-drawer__brief", "app-drawer__band"]
    assert [part["props"]["className"].split()[-1] for part in parts] == [
        *names,
        "app-drawer__actions",
    ]
    head = [kid for kid in parts[0]["props"]["children"] if kid is not None]
    assert parts[0]["type"] == "header"
    assert [kid.get("type") for kid in head] == ["img", "h2", None, "span", "p", "p"]
    assert head[0]["props"]["src"] == answers.DETAIL["logo"]
    assert text(head[1]) == answers.SYMBOL
    assert head[2]["props"] == {"phase": 4, "size": "sm", "children": []}
    assert text(head[3]) == "WIDE MOAT"
    assert text(head[4]) == "Lanternfield Optics Ltd"
    assert text(head[5]) == (
        "Reports in TWD; an ADR: every per-share figure is per ADS; valued at TWD 32.40 per USD"
    )
    assert head[5]["props"]["className"] == "caption app-muted app-drawer__currency"


def test_the_caption_is_the_sector_and_the_industry() -> None:
    """Joined by a middle dot, as the screen names them; the parts the company has; no caption
    with neither. The brief is not in it."""
    sector = _one(_drawn(answers.DETAIL), "app-drawer__sector")
    assert sector["type"] == "p"
    assert sector["props"]["className"] == "caption app-muted app-drawer__sector"
    assert text(sector) == "Technology · Semiconductors"
    company = answers.DETAIL["company"]
    energy = answers.detail(company=company | {"sector": "Energy", "industry": None})
    assert text(_one(_drawn(energy), "app-drawer__sector")) == "Energy"
    for unnamed in (company | {"sector": None, "industry": None}, None):
        assert classed(_drawn(answers.detail(company=unnamed)), "app-drawer__sector") == []


def test_the_brief_is_whole_and_cut_to_six_lines_by_the_style() -> None:
    """The whole stored brief, in body text; the style cuts it at six lines with an ellipsis. A
    company with no stored brief has none."""
    brief = _one(_drawn(answers.DETAIL), "app-drawer__brief")
    assert brief["type"] == "p"
    assert brief["props"]["className"] == "body app-drawer__brief"
    assert text(brief) == answers.DETAIL["brief"]
    assert classed(_drawn(answers.detail(brief=None)), "app-drawer__brief") == []
    rule = _rule(".app-drawer__brief {")
    for declaration in (
        "display: -webkit-box;",
        "-webkit-box-orient: vertical;",
        "-webkit-line-clamp: 6;",
        "line-clamp: 6;",
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
    detail = answers.detail()
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
    detail = answers.refused_detail()
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
    """In the band's place the refusal's sentence; no meter, no levels and no moat stamp."""
    tree = _drawn(answers.refused_detail())
    band = _one(tree, "app-drawer__band")
    refusal = _one(band, "app-refusal")
    assert (refusal["type"], refusal["props"]["className"]) == ("p", "body app-refusal")
    assert text(refusal) == answers.REFUSAL
    assert _meters(tree) == []
    assert classed(tree, "app-pairs") == []
    assert classed(tree, "app-moat") == []
    assert [part["props"]["className"].split()[-1] for part in tree if part is not None][-2:] == [
        "app-drawer__band",
        "app-drawer__actions",
    ]


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
    """The review counts: the meter and the levels are the review's, and the stamp the moat its
    override sets."""
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


def test_the_moat_stamp_follows_the_phase_badge() -> None:
    """Right after the phase badge, in the stamp's words; a company with no moat in force has no
    stamp, and a row with no phase no badge."""
    for moat, words in (("Wide", "WIDE MOAT"), ("Narrow", "NARROW MOAT"), ("None", "NO MOAT")):
        [head, *_] = _drawn(answers.detail(moat=moat))
        kids = head["props"]["children"]
        badge = next(i for i, kid in enumerate(kids) if kid and "phase" in kid["props"])
        assert kids[badge + 1] == node("moatStamp", [{"moat": moat}])
        assert text(kids[badge + 1]) == words
    [head, *_] = _drawn(answers.detail(moat=None))
    assert classed(head, "app-moat") == []
    unphased = answers.detail()
    unphased["result"]["phase"]["phase"] = None
    [head, *_] = _drawn(unphased)
    assert [kid for kid in head["props"]["children"] if kid and "phase" in kid["props"]] == []
    assert text(_one(head, "app-moat")) == "WIDE MOAT"
