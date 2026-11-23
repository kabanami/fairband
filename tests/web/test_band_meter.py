"""The band meter's head says price ÷ value and the value's name in one form, as the caller gives
it, and its caption only what the head does not (spec 2026-11-06 Tier 2, 18.2 item 2, plan 4); a
label on the tier above the track keeps its near edge 8px off the price marker (on QCOM the
marker's dot covered "$179.11"). The scale runs from 0.45 to 1.55 times the value, widened only for
a level outside it; a price beyond it is pinned at its end behind a break mark, and the band's two
labels sit outside their ticks (spec 2026-11-23 refresh experience, 4.7). The bundle runs in node
with a stub React (``render.mjs``), so the test reads the HTML ``BandMeter`` builds."""

import json
import re
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("render.mjs")
BUNDLE = (
    Path(str(resources.files("fairband.web").joinpath("static", "design-system", "components")))
    / "bundle.js"
)

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

QCOM = {
    "low": 179.11,
    "high": 242.32,
    "price": 173.19,
    "fairValue": 210.72,
    "buyLevel": 158.04,
    "trimLevel": 316.08,
    "designation": "below",
    "showScale": False,
}

AGILENT = {
    "low": 55.59,
    "high": 67.94,
    "fairValue": 61.77,
    "buyLevel": 43.24,
    "trimLevel": 83.39,
    "price": 170.38,
    "designation": "well-above",
}


def render(props: dict[str, Any]) -> str:
    """The HTML ``BandMeter`` builds from ``props``."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(HARNESS), str(BUNDLE), "BandMeter"],
        input=json.dumps(props),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return done.stdout


def test_the_head_says_the_gap_the_caller_gives() -> None:
    html = render({**QCOM, "gap": "0.82 × the reviewed value", "caption": "mechanical $342.38"})
    assert '<span class="fb-band__gap caption">0.82 × the reviewed value</span>' in html
    assert "fair value" not in html
    assert 'class="fb-band__caption caption">mechanical $342.38<' in html


def test_an_empty_gap_draws_no_gap_text() -> None:
    html = render({**QCOM, "gap": ""})
    assert "fb-band__gap" not in html


def test_without_a_gap_the_derived_text_stays() -> None:
    html = render(QCOM)
    assert "17.8% below fair value" in html


def _tier_label(html: str, text: str) -> tuple[str, dict[str, str]]:
    """The class of the tier label reading ``text`` and its style's properties."""
    found = re.search(rf'<span class="([^"]*)" style="([^"]*)">{re.escape(text)}</span>', html)
    assert found is not None, text
    pairs = (part.split(":", 1) for part in found[2].split(";"))
    return found[1], {name: value for name, value in pairs}


def test_each_tier_label_is_placed_off_the_price_marker() -> None:
    """Each band label says which end of the band it names and, for bundle.css, its tick, the
    price, its length in ch and the other label's (the tier is mono); the tier says where the
    price lies against the band. The stylesheet keeps the label outside its tick unless that
    brings its near edge within 8px of the marker, where it stops, and keeps the two 8px apart."""
    # QCOM: the price 173.19 lies under the band's low end
    html = render(QCOM)
    assert '<div class="fb-band__tier fb-band__tier--under figure-sm">' in html
    side, style = _tier_label(html, "$179.11")
    assert side == "fb-band__tier-label--low"
    assert list(style) == ["--tick", "--price", "--len", "--other"]
    assert style["--tick"].startswith("34.781") and style["--tick"].endswith("%")
    assert _placed(style["--price"]) == pytest.approx(32.338, abs=0.001)
    assert style["--len"] == "7ch" and style["--other"] == "7ch"
    side, style = _tier_label(html, "$242.32")
    assert side == "fb-band__tier-label--high"
    assert style["--tick"].startswith("60.866") and style["--len"] == "7ch"
    # the price just above the high end: the tier is over the band
    html = render({**QCOM, "price": 245.0, "designation": "above"})
    assert '<div class="fb-band__tier fb-band__tier--over figure-sm">' in html
    # the price on the low end's own position: inside the band
    html = render({**QCOM, "price": 179.11})
    assert '<div class="fb-band__tier fb-band__tier--in figure-sm">' in html
    for gone in ("--after", "--before", "tier-label--left", "tier-label--right"):
        assert gone not in html


def _marks(html: str, name: str) -> list[dict[str, Any]]:
    """Each element whose classes include ``name``: its ``class``, its ``style`` as a dict of its
    properties and its ``title`` (``None`` for none)."""
    found = []
    for tag in re.finditer(r'<(?:div|span) class="([^"]*)"((?: [a-z-]+="[^"]*")*)>', html):
        if name not in tag[1].split():
            continue
        given = dict(re.findall(r' ([a-z-]+)="([^"]*)"', tag[2]))
        style = given.get("style", "")
        pairs = (part.split(":", 1) for part in style.split(";") if part)
        found.append(
            {"class": tag[1], "style": dict(pairs), "title": given.get("title")},
        )
    return found


def _mark(html: str, name: str) -> dict[str, Any]:
    """The one element whose classes include ``name``."""
    [found] = _marks(html, name)
    return found


def _at(length: str) -> float:
    """A length given in % as its number."""
    assert length.endswith("%"), length
    return float(length.removesuffix("%"))


def _placed(length: str) -> float:
    """A marker's place inside the scale, ``clamp(7px, X%, calc(100% - 7px))``, as the number X:
    where its figure lies, but never nearer an end than a pinned marker stands."""
    found = re.fullmatch(r"clamp\(7px, (.+%), calc\(100% - 7px\)\)", length)
    assert found is not None, length
    return _at(found[1])


def test_the_scale_comes_from_the_value_not_the_price() -> None:
    """From 0.45 to 1.55 times the value: the fair value in the centre, the band about 18% of the
    width and the trim level at 82%, whatever the price."""
    for price in (170.38, 61.77):
        html = render({**AGILENT, "price": price})
        assert _at(_mark(html, "fb-band__fairmark")["style"]["left"]) == pytest.approx(50.0)
        bracket = _mark(html, "fb-band__bracket")["style"]
        assert _at(bracket["left"]) == pytest.approx(40.9, abs=0.01)
        assert _at(bracket["width"]) == pytest.approx(18.2, abs=0.03)
        fair = _mark(html, "fb-zone--fair")["style"]
        assert fair["left"] == bracket["left"] and fair["width"] == bracket["width"]
        assert _at(_mark(html, "fb-zone--trim")["style"]["left"]) == pytest.approx(81.8, abs=0.02)
        assert _at(_mark(html, "fb-zone--buy")["style"]["width"]) == pytest.approx(22.7, abs=0.03)


def test_a_price_beyond_the_scale_is_pinned_behind_a_break_mark() -> None:
    """A price beyond an end is pinned 7px in from that end, behind one break mark on the track;
    its title and the head keep the true price."""
    html = render(AGILENT)
    mark = _mark(html, "fb-band__price-mark")
    assert mark["class"] == "fb-band__price-mark fb-band__price-mark--pinned"
    assert mark["style"] == {"left": "calc(100% - 7px)"}
    assert mark["title"] == "Price $170.38 — Well above"
    assert '<span class="fb-band__price figure-lg">$170.38</span>' in html
    assert [b["class"] for b in _marks(html, "fb-band__break")] == [
        "fb-band__break fb-band__break--high"
    ]
    # the break is drawn on the track, before the marker
    track = html.index('class="fb-band__track"')
    assert track < html.index("fb-band__break") < html.index("fb-band__price-mark")
    # the labels read the pinned place, so they keep clear of the marker where it is drawn
    for text in ("$55.59", "$67.94"):
        assert _tier_label(html, text)[1]["--price"] == "calc(100% - 7px)"
    assert '<div class="fb-band__tier fb-band__tier--over figure-sm">' in html

    html = render({**AGILENT, "price": 12.40, "designation": "well-below"})
    mark = _mark(html, "fb-band__price-mark")
    assert mark["class"] == "fb-band__price-mark fb-band__price-mark--pinned"
    assert mark["style"] == {"left": "7px"}
    assert mark["title"] == "Price $12.40 — Well below"
    assert [b["class"] for b in _marks(html, "fb-band__break")] == [
        "fb-band__break fb-band__break--low"
    ]
    for text in ("$55.59", "$67.94"):
        assert _tier_label(html, text)[1]["--price"] == "7px"
    assert '<div class="fb-band__tier fb-band__tier--under figure-sm">' in html


def test_a_price_inside_the_scale_is_drawn_to_scale_with_no_break() -> None:
    """A price inside the scale, its ends included, is drawn where it lies, with no break mark."""
    html = render({**AGILENT, "price": 61.77, "designation": "near"})
    mark = _mark(html, "fb-band__price-mark")
    assert mark["class"] == "fb-band__price-mark"
    assert _placed(mark["style"]["left"]) == pytest.approx(50.0)
    assert "fb-band__break" not in html
    # the scale's ends, the same floats the bundle computes, are inside it
    for price, at in ((61.77 * 1.55, 100.0), (61.77 * 0.45, 0.0)):
        html = render({**AGILENT, "price": price})
        mark = _mark(html, "fb-band__price-mark")
        assert mark["class"] == "fb-band__price-mark", price
        assert _placed(mark["style"]["left"]) == pytest.approx(at, abs=1e-9)
        assert "fb-band__break" not in html


def test_a_marker_at_an_end_of_the_scale_keeps_its_dot_on_the_meter() -> None:
    """The look in a browser (2026-11-24): a price at 0.45 or 1.55 times the value, an end of the
    scale and so inside it, stood on the track's end, and its dot, 11px across with a 2px ring,
    hung 6.5px off the meter. A marker inside the scale stands where its figure lies but never
    nearer an end than the 7px a pinned one stands in, the price's and the reviewed value's
    alike; the band's labels read the same place, so they keep clear of the marker drawn."""
    for price in (61.77 * 1.55, 61.77 * 0.45, 61.77):
        html = render({**AGILENT, "price": price, "reviewedValue": price})
        for name in ("fb-band__price-mark", "fb-band__reviewed-mark"):
            left = _mark(html, name)["style"]["left"]
            assert left.startswith("clamp(7px, ") and left.endswith("%, calc(100% - 7px))"), left
        place = _mark(html, "fb-band__price-mark")["style"]["left"]
        for text in ("$55.59", "$67.94"):
            assert _tier_label(html, text)[1]["--price"] == place


def test_the_band_labels_sit_outside_their_ticks() -> None:
    """The low label ends at its tick and the high one starts at its tick (bundle.css), so each
    names its end and carries the other's length; the tier says where the price lies."""
    for price, side in ((50.00, "under"), (61.77, "in"), (80.00, "over")):
        html = render({**AGILENT, "price": price})
        assert f'<div class="fb-band__tier fb-band__tier--{side} figure-sm">' in html, price
        low_side, low = _tier_label(html, "$55.59")
        high_side, high = _tier_label(html, "$67.94")
        assert (low_side, high_side) == ("fb-band__tier-label--low", "fb-band__tier-label--high")
        assert _at(low["--tick"]) == pytest.approx(40.9, abs=0.01)
        assert _at(high["--tick"]) == pytest.approx(59.08, abs=0.01)
        assert low["--price"] == high["--price"]
    # labels of two lengths: each carries its own and the other's
    html = render({"low": 95.0, "high": 105.0, "fairValue": 100.0, "price": 100.0})
    low = _tier_label(html, "$95.00")[1]
    high = _tier_label(html, "$105.00")[1]
    assert (low["--len"], low["--other"]) == ("6ch", "7ch")
    assert (high["--len"], high["--other"]) == ("7ch", "6ch")


def test_a_level_outside_the_scale_widens_it() -> None:
    """A trim level at 1.8 times the value, past the scale's end, widens the scale to hold it with
    a tenth of the value beyond it; the price never does."""
    html = render({**AGILENT, "trimLevel": 111.19})
    assert _at(_mark(html, "fb-zone--trim")["style"]["left"]) == pytest.approx(93.1, abs=0.01)
    assert _mark(html, "fb-band__price-mark")["style"] == {"left": "calc(100% - 7px)"}
    # a buy level below the scale's low end widens it that way
    html = render({**AGILENT, "buyLevel": 12.35, "price": 61.77})
    buy = _at(_mark(html, "fb-zone--buy")["style"]["width"])
    assert buy == pytest.approx((12.35 - 6.173) / (95.7435 - 6.173) * 100, abs=0.01)


def test_a_meter_without_a_buy_or_a_trim_level_keeps_the_scale() -> None:
    """Without a buy level, a trim level or both, the scale is the value's as before."""
    for missing in (("buyLevel",), ("trimLevel",), ("buyLevel", "trimLevel")):
        props = {key: value for key, value in AGILENT.items() if key not in missing}
        html = render(props)
        assert _at(_mark(html, "fb-band__fairmark")["style"]["left"]) == pytest.approx(50.0)
        assert _at(_mark(html, "fb-band__bracket")["style"]["left"]) == pytest.approx(
            40.9, abs=0.01
        )
        assert _mark(html, "fb-band__price-mark")["style"] == {"left": "calc(100% - 7px)"}
        for key, zone in (("buyLevel", "fb-zone--buy"), ("trimLevel", "fb-zone--trim")):
            assert (zone in html) == (key not in missing), (missing, zone)


def test_a_value_at_or_below_zero_draws_no_nan() -> None:
    """A value at or below zero has no scale of its own: the meter spans every point with 12% of
    padding, as before, and pins nothing."""
    for props in (
        {"low": 0.0, "high": 0.0, "fairValue": 0.0, "price": 8.0},
        {"low": -15.0, "high": -10.0, "fairValue": -12.5, "price": 8.0, "reviewedValue": 4.0},
        {**AGILENT, "fairValue": 0.0},
    ):
        html = render(props)
        assert "NaN" not in html and "Infinity" not in html, props
        assert "fb-band__break" not in html and "--pinned" not in html, props
        assert _placed(_mark(html, "fb-band__price-mark")["style"]["left"]) <= 100.0


def test_a_reviewed_value_beyond_the_scale_is_pinned_as_the_price_is() -> None:
    """The reviewed value's marker takes the price's rule: to scale inside the scale, 7px in from
    the end beyond it, with no break mark of its own."""
    html = render({**AGILENT, "price": 61.77, "reviewedValue": 120.0})
    assert _mark(html, "fb-band__reviewed-mark")["style"] == {"left": "calc(100% - 7px)"}
    assert _mark(html, "fb-band__reviewed-mark")["title"] == "Reviewed value $120.00"
    assert "fb-band__break" not in html
    html = render({**AGILENT, "price": 61.77, "reviewedValue": 20.0})
    assert _mark(html, "fb-band__reviewed-mark")["style"] == {"left": "7px"}
    html = render({**AGILENT, "price": 170.38, "reviewedValue": 61.77})
    assert _placed(_mark(html, "fb-band__reviewed-mark")["style"]["left"]) == pytest.approx(50.0)
    assert [b["class"] for b in _marks(html, "fb-band__break")] == [
        "fb-band__break fb-band__break--high"
    ]
