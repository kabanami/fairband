"""The drawer's one line on the company (B-149): the sector and industry of the universe row,
then the first sentence of the company brief, the stored profile's description, joined by middle
dots; the full text is behind Details. The page's own script runs in node after the bundle
(``page.mjs``), and the test reads what ``briefLine`` and ``firstSentence`` return."""

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

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

COMPANY = {"sector": "Consumer Defensive", "industry": "Beverages - Non-Alcoholic"}
BRIEF = (
    "The Cola Company, a beverage company, makes and sells nonalcoholic beverages in the United "
    "States and internationally. The company provides sparkling soft drinks, water and juice."
)
FIRST = (
    "The Cola Company, a beverage company, makes and sells nonalcoholic beverages in the United "
    "States and internationally."
)


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


def test_the_line_is_the_sector_the_industry_and_the_first_sentence() -> None:
    assert _call("briefLine", COMPANY, BRIEF) == (
        "Consumer Defensive · Beverages - Non-Alcoholic · " + FIRST
    )


def test_the_line_without_a_brief_or_without_a_row() -> None:
    """A company without a stored profile keeps the sector and industry; a snapshot without a
    universe row keeps the first sentence; a row with neither name and no brief gives nothing,
    so the head draws no line."""
    assert _call("briefLine", COMPANY, None) == "Consumer Defensive · Beverages - Non-Alcoholic"
    assert _call("briefLine", {"sector": "Energy", "industry": None}, None) == "Energy"
    assert _call("briefLine", None, BRIEF) == FIRST
    assert _call("briefLine", {"sector": None, "industry": None}, None) == ""
    assert _call("briefLine", None, None) == ""


def test_the_first_sentence_ends_at_a_period_before_a_capital() -> None:
    """A sentence ends at the first period followed by white space and a capital letter; a
    period after an abbreviation (Co., Corp., Inc., Ltd., St., Dr. and the titles), a word with
    its own period or a single letter, or before a lower-case word, as in "Apple Inc. designs",
    does not end it. A brief with no such period is its own first sentence; white space around
    it goes."""
    assert _call("firstSentence", BRIEF) == FIRST
    assert _call("firstSentence", "Apple Inc. designs phones. The company sells them.") == (
        "Apple Inc. designs phones."
    )
    assert _call("firstSentence", "Acme sells in the U.S. The company is in Ohio. It is old.") == (
        "Acme sells in the U.S. The company is in Ohio."
    )
    assert _call("firstSentence", "Plan B. The company is new.") == "Plan B. The company is new."
    assert _call("firstSentence", "KKR & Co. Inc. is a firm. The firm invests.") == (
        "KKR & Co. Inc. is a firm."
    )
    assert _call("firstSentence", "The St. Joe Company owns land. It builds.") == (
        "The St. Joe Company owns land."
    )
    assert _call("firstSentence", "Eaton Corp. PLC makes parts. It sells.") == (
        "Eaton Corp. PLC makes parts."
    )
    assert _call("firstSentence", "  One sentence without a period  ") == (
        "One sentence without a period"
    )
    assert _call("firstSentence", "Two lines.\nThe second.") == "Two lines."
    assert _call("firstSentence", None) == ""
