"""The line under a report's title on the report page (spec 2026-11-15 7): the bundle's
``ReportReader`` draws the ``cites`` line from the dates the page passes, the data's, the price's,
the end of the validity window and the full report a valuation review reuses, each in words and
joined by the reader's ``·``, and names no part of Fairband and no record's id. The drawer's
Summary passes no ``cites`` and draws no line. The harness (``page.mjs``) calls the component with
its props and the tests read the tree it draws (``support.page``).

And Appendix A's record of an override the review applied at a split (spec 2026-11-15 8): the
page's script, report.js, builds it with the pair in force and the words of the scaling under it,
and the test reads the tree it builds.

And a cite's number in a report's table (spec 2026-11-15 9): ``ReportReader`` holds a cite and
its number in one span there, and nowhere else.

And Appendix A's Snapshot line (the whole-branch review's I1), which the export writes in the
same words."""

from typing import Any

import pytest
from support.page import NODE, STATIC, classed, elements, node, text

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


def _holder(tree: Any, child: dict[str, Any]) -> dict[str, Any]:
    """The element of ``tree`` whose children hold ``child``."""
    [held] = [e for e in elements(tree) if child in (e["props"].get("children") or [])]
    return held


def test_a_cite_in_a_table_keeps_its_number_and_one_outside_is_drawn_as_before() -> None:
    """Spec 2026-11-15 9: in a report's table a cite and its number ``[n]`` sit in one span,
    ``fb-cite__pair``, which the bundle's stylesheet does not let wrap, so the number never
    starts a line of its own. A cite with no number in a table, and a cite in a paragraph, are
    drawn as before: the cite and its number side by side in a Fragment, which has no type."""
    revenue = {"cite": "$10.44 billion", "ref": "fact:QCOM/revenue/2026Q4"}
    parts = [
        "Revenue was ",
        revenue,
        ".\n\n| | The quarter | A year before |\n|---|---|---|\n| Revenue | ",
        revenue,
        " | ",
        {"cite": "$11.27 billion", "ref": "fact:QCOM/revenue/2025Q4"},
        " |\n",
    ]
    tree = _draw(
        sections=[{"heading": "Summary", "parts": parts}],
        footnotes={"fact:QCOM/revenue/2026Q4": 3},
        appendixes=False,
    )
    [prose] = classed(tree, "fb-report__prose")
    [table] = classed(tree, "fb-report__table")
    # in the table: the cite with a number and its number in one span; the one without, alone
    quarter, year_before = classed(table, "fb-cite")
    [number] = classed(table, "fb-cite__n")
    [pair] = classed(table, "fb-cite__pair")
    assert pair["type"] == "span"
    assert pair["props"]["children"] == [quarter, number]
    assert text(pair) == "$10.44 billion[3]"
    alone = _holder(table, year_before)
    assert "type" not in alone and alone["props"]["children"] == [year_before, None]
    # in the paragraph: no span holds the two
    assert classed(prose, "fb-cite__pair") == []
    [cite] = classed(prose, "fb-cite")
    held = _holder(prose, cite)
    assert "type" not in held
    assert [text(child) for child in held["props"]["children"]] == ["$10.44 billion", "[3]"]
    assert text(prose) == "Revenue was $10.44 billion[3]."


SNAPSHOT = {
    "id": 412,
    "dataDate": "2026-11-04",
    "priceDate": "2026-11-04",
    "validUntil": "2027-01-27",
    "currency": "USD",
    "price": 150.0,
    "value": 128.0,
    "refusal": None,
}


def test_appendix_a_s_snapshot_line_names_another_currency_last() -> None:
    """The whole-branch review's I1: Appendix A's Snapshot part names the snapshot the report rests
    on and, on a company in another currency, the reporting currency its money figures are in
    (method 16.6), last, as the export's line does (report.js's ``snapshotLine``); a USD company's
    names none, and a missing date or figure is a dash."""

    def line(**changes: Any) -> str:
        return text(node("reportAppendix.snapshotLine", [SNAPSHOT | changes], STATIC / "report.js"))

    usd = (
        "Snapshot 412 · data 4 Nov 2026 · priced 4 Nov 2026 · valid until 27 Jan 2027"
        " · price $150.00 · value $128.00"
    )
    assert line() == usd
    assert line(currency="SEK") == usd + " · in SEK"
    assert line(priceDate=None, value=None).endswith(
        " · priced — · valid until 27 Jan 2027 · price $150.00 · value —"
    )


def _override(override_id: int, tag: str, unit: str, old: float, new: float) -> dict[str, Any]:
    """An entry of Appendix A's overrides as the server sends it, applied as entered."""
    return {
        "id": override_id,
        "tag": tag,
        "old": old,
        "new": new,
        "unit": unit,
        "reason": "a stake",
        "evidence": [{"kind": "transcript", "ref": "Q3 call", "note": ""}],
        "lifetime": "lasting",
        "period": None,
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "at": "2026-11-06T09:30:00+00:00",
        "inForce": None,
        "rescaled": None,
    }


def test_an_override_scaled_at_a_split_shows_the_figures_in_force_and_the_words() -> None:
    """Spec 2026-11-15 8: on the report page, Appendix A's record of an override the review applied
    at a split, $30.00 entered before a 2-for-1 split, shows the pair in force, $5.90 → $15.00,
    both on the new basis, with the words of the scaling under it as the server sends them; one
    applied as entered shows its stored pair and no words (report.js's ``overrides``, its tree as
    the page's script builds it)."""
    words = "entered as $30.00 a share before the 2-for-1 split of 27 Jan 2027"
    scaled = _override(1, "earnings.ntm", "USD a share", 11.8, 30.0)
    scaled |= {"inForce": {"old": 5.9, "new": 15.0}, "rescaled": words}
    lines = [
        {"overrideId": 1, "old": 5.9, "new": 15.0, "delta": 196.92, "refusal": None},
        {"overrideId": 2, "old": 0.063, "new": 0.08, "delta": 12.5, "refusal": None},
    ]
    a = {
        "snapshot": {"validUntil": "2027-04-29"},
        "bridge": {"reviewId": 9, "reviewedValue": 337.1, "lines": lines},
        "overrides": [scaled, _override(2, "growth.belief", "ratio", 0.063, 0.08)],
    }
    tree = node("reportAppendix.overrides", [a], STATIC / "report.js")
    records = [e["props"] for e in elements(tree) if "from" in e["props"]]
    assert [(r["tag"], r["from"], r["to"]) for r in records] == [
        ("earnings.ntm", "$5.90", "$15.00"),
        ("growth.belief", "6.3%", "8.0%"),
    ]
    assert [r["effect"] for r in records] == [196.92, 12.5]
    [entered] = classed(tree, "app-report__entered")
    assert text(entered) == words  # as the server sends them, never rewritten
    assert "$11.80" not in str(tree)


def test_a_step_refused_at_a_split_shows_the_figures_in_force_beside_its_refusal() -> None:
    """A step refused at the figure in force (spec 2026-11-15 8, the Task 7 review's ruling): the
    record shows the pair in force, $5.90 → −$1.00, its Result the step's refusal, and the words
    under it, in a review whose last step refused and so has no value."""
    words = "entered as −$2.00 a share before the 2-for-1 split of 27 Jan 2027"
    refused = _override(1, "earnings.ntm", "USD a share", 11.8, -2.0)
    refused |= {"inForce": {"old": 5.9, "new": -1.0}, "rescaled": words}
    why = "no positive forward anchor"
    line = {"overrideId": 1, "old": 5.9, "new": -1.0, "delta": None, "refusal": why}
    a = {
        "snapshot": {"validUntil": "2027-04-29"},
        "bridge": {"reviewId": 9, "reviewedValue": None, "refusal": why, "lines": [line]},
        "overrides": [refused],
    }
    tree = node("reportAppendix.overrides", [a], STATIC / "report.js")
    [record] = [e["props"] for e in elements(tree) if "from" in e["props"]]
    assert (record["from"], record["to"], record["resultNote"]) == ("$5.90", "−$1.00", why)
    assert record.get("effect") is None
    [entered] = classed(tree, "app-report__entered")
    assert text(entered) == words
