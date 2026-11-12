"""What the price needs, on the drawer and the report page (method 4.11): where the company's
detail carries ``priceNeeds``, both lead the band with it, above the meter; without it they draw
nothing in its place. The page's own script runs in node after the bundle (``page.mjs``)."""

import json
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("page.mjs")
STATIC = Path(str(resources.files("fairband.web").joinpath("static")))
BUNDLE = STATIC / "design-system" / "components" / "bundle.js"
APP = STATIC / "app.js"
REPORT = STATIC / "report.js"
INDEX = STATIC / "index.html"

NEEDS = "The price needs long-run earnings growth of 11.9% a year to year 20. The route holds 5.3%."


def _call(helper: str, *args: Any) -> Any:
    """What app.js's ``helper`` returns on ``args``, through JSON."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(HARNESS), str(BUNDLE), str(APP), helper],
        input=json.dumps(list(args)),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_sentence_is_one_paragraph_of_body_text() -> None:
    line = _call("priceNeeds", {"priceNeeds": NEEDS})
    assert line["type"] == "p"
    assert line["props"]["className"] == "body app-needs"
    assert line["props"]["children"] == [NEEDS]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("body", [{"priceNeeds": None}, {}])
def test_a_detail_without_the_sentence_draws_nothing(body: dict[str, Any]) -> None:
    assert _call("priceNeeds", body) is None


def _function(source: str, name: str) -> str:
    """The text of the top-level function ``name`` in ``source``, to the next one."""
    start = source.index(f"\n  function {name}(")
    end = source.index("\n  function ", start + 1)
    return source[start:end]


def test_the_drawer_leads_the_band_with_it() -> None:
    """Under the head and above every band the drawer can draw: the route's, a refused row's
    review's and its secondary valuation's."""
    sections = _function(APP.read_text(encoding="utf-8"), "sections")
    needs = sections.index("priceNeeds(body),")
    assert sections.index("className: 'app-drawer__head'") < needs
    for band in ("section('band'", "section('review-band'", "section('secondary-band'"):
        assert needs < sections.index(band), band
    assert "priceNeeds: priceNeeds" in APP.read_text(encoding="utf-8")  # the report page's


def test_the_report_page_leads_the_band_with_it() -> None:
    band = _function(REPORT.read_text(encoding="utf-8"), "band")
    assert band.index("P.priceNeeds(d),") < band.index("P.meter(d, false),")


def test_the_sentence_has_its_style() -> None:
    assert ".app-needs {" in INDEX.read_text(encoding="utf-8")
