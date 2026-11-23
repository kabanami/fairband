"""The held value's one line, its detail and Review again (spec 2026-11-23 held reviewed value,
5.7; ``app.js``, ``heldLine`` and ``heldPart``), run in node as the page loads them, and the
row's mark in the design system's table."""

import copy
from typing import Any

import pytest
from support import page_answers as answers
from support.page import BUNDLE, NODE, STATIC, classed, elements, node, text

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

REASONS = [
    "Override 37 (consensus step 2) no longer applies: the input the override corrected changed.",
    "Override 38 (consensus step 3) no longer applies: the input the override corrected changed.",
    "Override 36 (non-recurring gap) no longer applies: the input the override corrected changed.",
]
READING = "Computed again on today's data, the review gives $291.62 (+7.0%)."
HELD: dict[str, Any] = {
    "state": "expired-early",
    "earlyAt": "2026-11-14",
    "reasons": REASONS,
    "reading": 291.62,
    "readingRefusal": None,
    "readingLine": READING,
    "validUntil": "2027-02-01",
}
AGAIN = {"$page": "reload"}  # any function of the page's stands for the button's handler


def _line(
    held: dict[str, Any] | None, view: dict[str, Any] | None = None, again: Any = None
) -> Any:
    return node("heldLine", [held, view or {}, None, again])


def _button_words(tree: Any) -> list[str]:
    return [text(e) for e in elements(tree) if e.get("type") == "button"]


def _offers_again(tree: Any) -> bool:
    """Whether the tree holds the Review again button, the design system's Button, which the
    harness leaves undrawn: an element with no type whose words are the button's."""
    return any(e.get("type") is None and text(e) == "Review again" for e in elements(tree))


def test_the_line_is_absent_for_a_value_that_is_not_expired_early() -> None:
    """Spec 5.7: the drawer and the Overview add nothing for a value that is current, aging or
    expired by its date, and nothing for a row with no held record."""
    for state in ("current", "aging", "expired"):
        assert _line(HELD | {"state": state, "reasons": []}) is None, state
    assert _line(None) is None


def test_the_line_names_the_day_and_counts_the_reasons() -> None:
    """One line, a button that says whether its detail is open: Expired's glyph, the day a
    refresh first found a reason, and the count of the reasons, which leaves the reading out
    when it is none. Closed, it shows nothing else."""
    line = _line(HELD)
    [button] = [e for e in elements(line) if e.get("type") == "button"]
    assert text(button) == "× Expired early 14 Nov 2026 · 3 reasons ▸"
    assert button["props"]["aria-expanded"] is False
    [mark] = classed(line, "fb-mark--expired")
    assert text(mark) == "×"
    assert classed(line, "app-held__detail") == []
    one = _line(HELD | {"reasons": REASONS[:1], "earlyAt": None, "readingLine": None})
    assert _button_words(one) == ["× Expired early · 1 reason ▸"]


def test_the_opened_detail_lists_the_reasons_then_the_reading() -> None:
    """A click opens the detail: the reasons, one a line, in the order given, then the reading's
    line where it is no reason. Nothing else on the page shows the reading."""
    line = _line(HELD, {"open": True})
    [button] = [e for e in elements(line) if e.get("type") == "button"]
    assert text(button) == "× Expired early 14 Nov 2026 · 3 reasons ▾"
    assert button["props"]["aria-expanded"] is True
    [detail] = classed(line, "app-held__detail")
    assert [text(p) for p in elements(detail) if p.get("type") == "p"] == [*REASONS, READING]


def test_review_again_is_offered_for_a_review_and_shows_a_refusal() -> None:
    """Spec 5.6 and 5.7: the opened detail of a review ends with Review again; a secondary
    valuation's has none, an agent makes it again. A refusal's sentence shows in the detail."""
    assert _offers_again(_line(HELD, {"open": True}, AGAIN))
    assert not _offers_again(_line(HELD, {"open": True}))
    assert not _offers_again(_line(HELD, {}, AGAIN))  # closed: the line alone
    refused = _line(HELD, {"open": True, "error": "settings changed: run a revalue"}, AGAIN)
    [sentence] = classed(refused, "app-refusal")
    assert text(sentence) == "settings changed: run a revalue"
    assert node("reviewAgainUrl", ["A&B"]) == "/api/companies/A%26B/review"
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "api.post(reviewAgainUrl(symbol))" in script  # the button posts to the route


def test_the_drawer_draws_the_line_under_the_levels_of_a_value_expired_early() -> None:
    """The drawer's band section ends with the line where its reviewed value expired early, and
    has none where the held review is current."""
    current = answers.reviewed_detail()
    current["review"] = current["review"] | {"held": HELD | {"state": "current", "reasons": []}}
    assert classed(node("sections", [current]), "app-held") == []
    early = copy.deepcopy(current)
    early["review"]["held"] = HELD
    [band] = classed(node("sections", [early]), "app-drawer__band")
    [held] = classed(band, "app-held")
    assert _button_words(held) == ["× Expired early 14 Nov 2026 · 3 reasons ▸"]


def test_a_held_secondary_valuation_draws_its_band_on_a_row_the_route_values() -> None:
    """Spec 5.9: a secondary valuation that holds its row keeps the band, the levels and the
    line after the route values the company, as the screen's row does: the drawer draws the
    secondary's value, with the mechanical value in its caption, and offers no Review again."""
    reason = "The route now values the company, at $196.50."
    secondary = {
        "id": 4,
        "form": "parts",
        "valuePerShare": 120.0,
        "levels": {"buy": 96.0, "fairLow": 108.0, "fairHigh": 132.0, "trim": 162.0},
        "priceToValue": 1.5,
        "designation": "well-above",
        "parts": [],
        "drivers": None,
        "createdAt": "2026-11-11T12:00:00+00:00",
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "held": HELD | {"earlyAt": None, "reasons": [reason], "readingLine": None},
    }
    detail = answers.detail(secondary=secondary)
    assert node("bandBasis", [detail]) == "reviewed"
    rows = node("levelRows", [detail])
    assert [name for name, _ in rows] == ["Fair value", "Buy level", "Fair band", "Trim level"]
    assert rows[0][1] == "$120.00" and rows[1][1] == "$96.00"
    meter = node("meter", [detail, False])
    assert "mechanical $196.50" in text(meter) or "mechanical $196.5" in str(meter)
    [band] = classed(node("sections", [detail]), "app-drawer__band")
    [held] = classed(band, "app-held")
    assert _button_words(held) == ["× Expired early · 1 reason ▸"]
    opened = node("heldLine", [secondary["held"], {"open": True}, None, None])
    assert not _offers_again(opened)  # an agent makes a secondary valuation again
    # a secondary valuation made on a valued snapshot holds no row: the band stays the engine's
    legacy = answers.detail(secondary=secondary | {"held": None})
    assert node("bandBasis", [legacy]) == "mechanical"
    assert classed(node("sections", [legacy]), "app-held") == []


def test_the_row_s_mark_reads_expired_early() -> None:
    """Spec 5.7: "Expired early" takes the glyph and the colour of Expired. The table's mark, in
    the vendored design system, reads the row's ``expiredEarly`` for its words."""
    bundle = BUNDLE.read_text(encoding="utf-8")
    assert "r.expiredEarly ? 'Expired early' : FRESHNESS[f].word" in bundle


def test_the_reviewed_cell_carries_the_mark_of_a_value_expired_early() -> None:
    """Spec 2, the anti-goals: each reason must show on the row on the day it holds. The table's
    Entered column, which carries the freshness mark, is not among the columns the screen opens
    with, so the Reviewed cell carries Expired's glyph, in its colour, with the words "Expired
    early", beside the figure of a value that expired early."""
    bundle = BUNDLE.read_text(encoding="utf-8")
    assert (
        "r.expiredEarly ? h('span', { className: 'fb-mark fb-mark--expired', "
        "title: 'Expired early' }, FRESHNESS.expired.mark) : null"
    ) in " ".join(bundle.split())


def test_the_line_is_set_in_the_caption_s_type() -> None:
    """The line is a caption, as the levels' names above it are: the button takes the design
    system's caption type, not the browser's own for a button, nor the body's."""
    css = (STATIC / "index.html").read_text(encoding="utf-8")
    start = css.index(".app-held__line {")
    rule = " ".join(css[start : css.index("}", start)].split())
    assert "font: inherit" not in rule and "font-size" not in rule
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "className: 'app-held__line caption'" in script
