"""The line under a report's title on the report page (spec 2026-11-15 7): the bundle's
``ReportReader`` draws the ``cites`` line from the dates the page passes, the data's, the price's,
the end of the validity window and the full report a valuation review reuses, each in words and
joined by the reader's ``·``, and names no part of Fairband and no record's id. The drawer's
Summary passes no ``cites`` and draws no line. The harness (``page.mjs``) calls the component with
its props and the tests read the tree it draws (``support.page``)."""

from typing import Any

import pytest
from support.page import NODE, classed, elements, node, text

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SECTIONS = [{"heading": "Summary", "parts": ["Plain words."]}]


def _draw(**props: Any) -> Any:
    """The tree the bundle's ``ReportReader`` draws for a published report on ``props``."""
    given = {"state": "published", "revision": "revision 1", "sections": SECTIONS} | props
    return node("Fairband.ReportReader", [given])


def _line(cites: dict[str, Any]) -> str:
    """The reader's line under the title on ``cites``."""
    [line] = classed(_draw(cites=cites), "fb-report__cites")
    return text(line)


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
    [line] = classed(_draw(cites=cites), "fb-report__cites")
    times = [e for e in elements(line) if e.get("type") == "time"]  # a Fragment has no type
    assert [(t["props"]["dateTime"], text(t)) for t in times] == [
        ("2026-11-04", "4 Nov 2026"),
        ("2026-11-03", "3 Nov 2026"),
        ("2027-01-27", "27 Jan 2027"),
    ]


def test_the_drawer_s_summary_draws_no_line() -> None:
    """Without ``cites``, as the drawer's Summary passes it, the reader draws no line under the
    title and the section as before."""
    tree = _draw(appendixes=False)
    assert classed(tree, "fb-report__cites") == []
    [section] = classed(tree, "fb-report__section")
    assert text(section) == "SummaryPlain words."
