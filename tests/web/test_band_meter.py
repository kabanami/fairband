"""The band meter's head says price ÷ value and the value's name in one form, as the caller gives
it, and its caption only what the head does not (spec 2026-11-06 Tier 2, 18.2 item 2, plan 4); a
label on the tier above the track within six points of the price marker is anchored away from it
(on QCOM the marker's dot covered "$179.11"). The bundle runs in node with a stub React
(``render.mjs``), so the test reads the HTML ``BandMeter`` builds."""

import json
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


def test_a_label_near_the_price_marker_is_anchored_away_from_it() -> None:
    # the price 173.19 sits 3.0 points of the axis left of the low label 179.11: it anchors after
    html = render(QCOM)
    assert 'class="fb-band__tier-label--after"' in html and "$179.11" in html
    assert "fb-band__tier-label--before" not in html
    # the price just above the high label: that label anchors before
    html = render({**QCOM, "price": 245.0, "designation": "above"})
    assert 'class="fb-band__tier-label--before"' in html
    # the price on the label's own position anchors after
    html = render({**QCOM, "price": 179.11})
    assert 'class="fb-band__tier-label--after"' in html
    # a price far from both labels: no anchor class
    html = render({**QCOM, "price": 100.0, "designation": "well-below"})
    assert "fb-band__tier-label--" not in html
