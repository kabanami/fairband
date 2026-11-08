"""The band meter's head says price ÷ value and the value's name in one form, as the caller gives
it, and its caption only what the head does not (spec 2026-11-06 Tier 2, 18.2 item 2, plan 4); a
label on the tier above the track is placed on its side of the price marker, its near edge never
nearer the marker than 8px (on QCOM the marker's dot covered "$179.11"). The bundle runs in node
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
    """Each tier label carries its side of the price marker and, for bundle.css, its tick, the
    price and its length in ch (the tier is mono): the stylesheet centres it on its tick unless
    that brings its near edge within 8px of the marker, where it stops."""
    # QCOM: the price 173.19 lies left of both labels, so both sit right of the marker
    html = render(QCOM)
    low = re.search(
        r'<span class="fb-band__tier-label--right" style="([^"]*)">\$179\.11</span>', html
    )
    assert low is not None and "--len:7ch" in low[1]
    side, style = _tier_label(html, "$179.11")
    assert list(style) == ["--tick", "--price", "--len"]
    assert style["--tick"].startswith("20.429") and style["--tick"].endswith("%")
    assert style["--price"].startswith("17.408") and style["--price"].endswith("%")
    side, style = _tier_label(html, "$242.32")
    assert side == "fb-band__tier-label--right"
    assert style["--tick"].startswith("52.684") and style["--len"] == "7ch"
    assert "tier-label--left" not in html
    # the price just above the high label: that label sits left of the marker
    html = render({**QCOM, "price": 245.0, "designation": "above"})
    assert _tier_label(html, "$242.32")[0] == "fb-band__tier-label--left"
    # the price on the low label's own position: that label sits right of the marker
    html = render({**QCOM, "price": 179.11})
    assert _tier_label(html, "$179.11")[0] == "fb-band__tier-label--right"
    for gone in ("tier-label--after", "tier-label--before"):
        assert gone not in html
