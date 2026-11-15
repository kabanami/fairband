"""The line under a report's title on the report page (spec 2026-11-15 7): the bundle's
``ReportReader`` draws the ``cites`` line from the dates the page passes, the data's, the price's,
the end of the validity window and the full report a valuation review reuses, each in words and
joined by the reader's ``·``, and names no part of Fairband and no record's id. The drawer's
Summary passes no ``cites`` and draws no line. The harness (``page.mjs``) calls the component with
its props and the tests read the tree it draws."""

import json
import shutil
import subprocess
from collections.abc import Iterator
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("page.mjs")
STATIC = Path(str(resources.files("fairband.web").joinpath("static")))
BUNDLE = STATIC / "design-system" / "components" / "bundle.js"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SECTIONS = [{"heading": "Summary", "parts": ["Plain words."]}]


def _draw(**props: Any) -> Any:
    """The tree the bundle's ``ReportReader`` draws for a published report on ``props``."""
    assert NODE is not None
    given = {"state": "published", "revision": "revision 1", "sections": SECTIONS} | props
    done = subprocess.run(
        [NODE, str(HARNESS), str(BUNDLE), str(STATIC / "app.js"), "Fairband.ReportReader"],
        input=json.dumps([given]),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


def _elements(node: Any) -> Iterator[dict[str, Any]]:
    """Every element of a drawn tree, in the document's order."""
    if isinstance(node, list):
        for child in node:
            yield from _elements(child)
    elif isinstance(node, dict):
        yield node
        yield from _elements(node["props"].get("children"))


def _classed(tree: Any, name: str) -> list[dict[str, Any]]:
    """The elements whose class list holds ``name``, in order."""
    return [e for e in _elements(tree) if name in str(e["props"].get("className") or "").split()]


def _text(node: Any) -> str:
    """The text an element holds."""
    if isinstance(node, list):
        return "".join(_text(child) for child in node)
    if isinstance(node, dict):
        return _text(node["props"].get("children"))
    return "" if node is None else str(node)


def _line(cites: dict[str, Any]) -> str:
    """The reader's line under the title on ``cites``."""
    [line] = _classed(_draw(cites=cites), "fb-report__cites")
    return _text(line)


@pytest.mark.parametrize(
    ("cites", "words"),
    [
        (
            {"dataDate": "2026-11-04", "priceDate": "2026-11-04", "validUntil": "2027-01-27"},
            "On the data of 4 Nov 2026 · priced that day · valid until 27 Jan 2027",
        ),
        (
            {"dataDate": "2026-11-04", "priceDate": "2026-11-03", "validUntil": "2027-01-27"},
            "On the data of 4 Nov 2026 · priced 3 Nov 2026 · valid until 27 Jan 2027",
        ),
        (
            {"dataDate": "2026-11-04", "priceDate": None, "validUntil": "2027-01-27"},
            "On the data of 4 Nov 2026 · valid until 27 Jan 2027",
        ),
        (
            {"dataDate": "2026-11-04", "priceDate": "2026-11-04", "validUntil": None},
            "On the data of 4 Nov 2026 · priced that day",
        ),
        (
            {
                "dataDate": "2026-11-04",
                "priceDate": "2026-11-04",
                "validUntil": "2027-01-27",
                "reusesFullReportOf": "2026-11-03",
            },
            (
                "On the data of 4 Nov 2026 · priced that day · valid until 27 Jan 2027 · reuses the"
                " full report of 3 Nov 2026"
            ),
        ),
    ],
)
def test_the_line_under_the_title_says_what_the_report_rests_on_in_words(
    cites: dict[str, Any], words: str
) -> None:
    line = _line(cites)
    assert line == words
    for name in ("snapshot", "review", "thesis"):
        assert name not in line, name


def test_the_line_writes_each_date_as_a_time() -> None:
    """Each date is the bundle's ``DateText``: a ``time`` whose machine date is the ISO day."""
    cites = {"dataDate": "2026-11-04", "priceDate": "2026-11-03", "validUntil": "2027-01-27"}
    [line] = _classed(_draw(cites=cites), "fb-report__cites")
    times = [e for e in _elements(line) if e.get("type") == "time"]  # a Fragment has no type
    assert [(t["props"]["dateTime"], _text(t)) for t in times] == [
        ("2026-11-04", "4 Nov 2026"),
        ("2026-11-03", "3 Nov 2026"),
        ("2027-01-27", "27 Jan 2027"),
    ]


def test_the_drawer_s_summary_draws_no_line() -> None:
    """Without ``cites``, as the drawer's Summary passes it, the reader draws no line under the
    title and the section as before."""
    tree = _draw(appendixes=False)
    assert _classed(tree, "fb-report__cites") == []
    [section] = _classed(tree, "fb-report__section")
    assert _text(section) == "SummaryPlain words."
