"""The drawer's "Intermediate results" for the three intermediates the research round adds (spec
2026-11-13 11 and 11a, 7.2): ``margin_history``'s medians as percentages, as ``median_margin``
reads, its counts of years whole, and no heading for an empty record; ``trailing_end`` as its ISO
date, as ``fx_date`` reads; ``sbc_ttm`` as a total in the row's currency at any size, nil
included, as ``ntm_net_income`` reads. Each label is the intermediate's key, as every other
label of the section is. The page's own script runs in node after the bundle (``page.mjs``), and
the tests read what ``intermediates`` returns."""

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
GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

MARGINS = {
    "operating": {"median": 0.2325, "years": 10},
    "net": {"median": 0.174375, "years": 10},
}


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


def _texts(node: Any) -> list[str]:
    """The text of an element tree, in order: its strings and its children's."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [text for child in node for text in _texts(child)]
    if isinstance(node, dict):
        return _texts(node.get("props", {}).get("children", []))
    return []


def _after(texts: list[str], label: str) -> str:
    """The text that follows ``label``: a figure after its name."""
    return texts[texts.index(label) + 1]


def _shown(im: dict[str, Any]) -> list[str]:
    return _texts(_call("intermediates", im))


def test_the_ten_year_median_margins_read_as_percentages() -> None:
    """Each median prints as ``median_margin`` prints the same figure, a percentage to one
    decimal; each count of years whole; the record under its key's heading."""
    texts = _shown({"median_margin": 0.2325, "margin_history": MARGINS})
    assert "margin_history" in texts  # the group's heading
    assert _after(texts, "operating.median") == _after(texts, "median_margin")
    assert _after(texts, "operating.median").endswith("%")
    assert _after(texts, "net.median") == "17.4%"
    assert _after(texts, "operating.years") == "10"
    assert _after(texts, "net.years") == "10"
    # MSCO's golden: the route's own median and the record's operating one read alike, 20.0%
    msco = json.loads((GOLDEN / "MSCO.json").read_text())["intermediates"]
    stable = _shown(msco)
    assert _after(stable, "operating.median") == _after(stable, "median_margin") == "20.0%"


def test_an_empty_margin_record_has_no_heading() -> None:
    """SUCO has no fiscal year with a revenue above zero, so its record is empty: the drawer shows
    no group for it, heading or rows."""
    suco = json.loads((GOLDEN / "SUCO.json").read_text())["intermediates"]
    assert suco["margin_history"] == {}
    texts = _shown(suco)
    assert "margin_history" not in texts
    assert "burn_cover_years" in texts  # the rest of the section stands


def test_the_trailing_end_and_the_stock_pay_read_as_their_neighbours() -> None:
    """``trailing_end`` is an ISO date, as ``fx_date``; ``sbc_ttm`` a total in the row's currency,
    as ``ntm_net_income``, at any size: MGCO's $400 m, FXCO's SEK 320 m, and a stock pay of nil
    or below a million, which the rule for an unnamed total at a million or more would leave a
    bare decimal."""
    mgco = json.loads((GOLDEN / "MGCO.json").read_text())["intermediates"]
    usd = _shown(mgco)
    assert _after(usd, "trailing_end") == "2026-09-30"
    assert _after(usd, "sbc_ttm") == "$400,000,000"
    assert _after(usd, "ntm_net_income").startswith("$")
    fxco = json.loads((GOLDEN / "FXCO.json").read_text())["intermediates"]
    sek = _shown(fxco)
    assert _after(sek, "sbc_ttm") == "SEK 320,000,000"
    assert _after(sek, "fx_date") == "2026-10-31"
    assert _after(_shown(mgco | {"sbc_ttm": 0.0}), "sbc_ttm") == "$0"
    assert _after(_shown(mgco | {"sbc_ttm": 500_000.0}), "sbc_ttm") == "$500,000"
    assert _after(_shown(fxco | {"sbc_ttm": 0.0}), "sbc_ttm") == "SEK 0"
