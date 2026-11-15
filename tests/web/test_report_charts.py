"""The report page's ROIC chart on a year whose average invested capital is at or below zero
(B-8, the founder's ruling of 2026-11-15; method 16.6): the year's figure has the wrong sign and
no meaning, so the chart leaves it out and a line under it names the years and why. charts.js
runs in node after the bundle and app.js (``page.mjs``), and the test reads what its
``roicPoints`` makes of the returns table's two rows.

And the bundle's ``HistoryBars`` on a bar that is not a fiscal year (spec 2026-11-15 6.6): the
trailing twelve months in the de-emphasis grey, an analysts' estimate an outline, the value on
the last bar that is not an estimate, the accessible name by what the bars run by and the table
twin by each point's label. The harness calls the component with its props and the tests read
the tree it draws."""

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
NOTE = "average invested capital is at or below zero"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _node(helper: str, args: list[Any], *scripts: Path) -> Any:
    """What ``helper``, as the harness names it, returns on ``args``, through JSON."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(HARNESS), str(BUNDLE), str(STATIC / "app.js"), helper]
        + [str(script) for script in scripts],
        input=json.dumps(args),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


def _call(helper: str, *args: Any) -> Any:
    """What charts.js's ``helper`` returns on ``args``, through JSON."""
    return _node(helper, list(args), STATIC / "charts.js")


def _row(values: list[float | None], notes: dict[str, str] | None = None) -> dict[str, Any]:
    """A table row over fiscal 2021 to 2025, each cell as the financial tables' read serves it."""
    cells = [
        {"period": str(2021 + k), "value": v, "unit": "percent", "ref": None, "note": None}
        for k, v in enumerate(values)
    ]
    for cell in cells:
        cell["note"] = (notes or {}).get(cell["period"])
    return {"name": "row", "unit": "percent", "cells": cells}


HURDLE = _row([0.09] * 5)


def test_a_year_on_capital_at_or_below_zero_is_left_out_and_named() -> None:
    roic = _row([0.20, 0.25, 0.30, -37.4, -71.1], {"2024": NOTE, "2025": NOTE})
    drawn = _call("reportCharts.roicPoints", roic, HURDLE)
    assert [p["period"] for p in drawn["series"]] == ["2021", "2022", "2023"]
    assert drawn["series"][0] == {"period": "2021", "roic": pytest.approx(20.0), "wacc": 9.0}
    assert drawn["left"] == (
        "Fiscal 2024 and 2025 are not drawn: average invested capital is at or below zero."
    )


def test_one_year_left_out_reads_in_the_singular() -> None:
    roic = _row([0.20, 0.25, 0.30, 0.31, -71.1], {"2025": NOTE})
    drawn = _call("reportCharts.roicPoints", roic, HURDLE)
    assert len(drawn["series"]) == 4
    assert drawn["left"] == (
        "Fiscal 2025 is not drawn: average invested capital is at or below zero."
    )


def test_a_row_without_such_a_year_draws_every_point_and_says_nothing() -> None:
    drawn = _call("reportCharts.roicPoints", _row([0.20, None, 0.30, 0.31, 0.32]), HURDLE)
    assert [p["period"] for p in drawn["series"]] == ["2021", "2023", "2024", "2025"]  # a gap
    assert drawn["left"] is None
    assert _call("reportCharts.roicPoints", None, HURDLE) == {"series": [], "left": None}


def test_every_year_left_out_leaves_no_point_and_the_sentence() -> None:
    """The panel then shows the sentence in place of "No data on file." (``spread``)."""
    notes = {str(year): NOTE for year in range(2021, 2026)}
    drawn = _call("reportCharts.roicPoints", _row([-1.0, -2.0, -3.0, -4.0, -5.0], notes), HURDLE)
    assert drawn["series"] == []
    assert drawn["left"] == (
        "Fiscal 2021, 2022, 2023, 2024 and 2025 are not drawn: "
        "average invested capital is at or below zero."
    )


def test_a_year_on_capital_of_exactly_zero_has_no_figure_and_is_named_too() -> None:
    """At exactly zero the engine's ROIC is none and the cell still carries the note
    (``tables.NO_CAPITAL``): the export writes the note, so the page names the year."""
    roic = _row([0.20, 0.25, 0.30, None, 0.31], {"2024": NOTE})
    drawn = _call("reportCharts.roicPoints", roic, HURDLE)
    assert [p["period"] for p in drawn["series"]] == ["2021", "2022", "2023", "2025"]
    assert drawn["left"] == (
        "Fiscal 2024 is not drawn: average invested capital is at or below zero."
    )


def test_three_years_left_out_are_listed_with_commas() -> None:
    notes = {"2023": NOTE, "2024": NOTE, "2025": NOTE}
    drawn = _call("reportCharts.roicPoints", _row([0.2, 0.2, -5.0, -6.0, -7.0], notes), HURDLE)
    assert drawn["left"] == (
        "Fiscal 2023, 2024 and 2025 are not drawn: average invested capital is at or below zero."
    )


def _draw(**props: Any) -> Any:
    """The tree the bundle's ``HistoryBars`` draws on ``props``, every component in it called."""
    return _node("Fairband.HistoryBars", [{"title": "Revenue", **props}])


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


def _bars(tree: Any) -> list[str]:
    """The bars' class lists, in order."""
    return [e["props"]["className"] for e in _classed(tree, "fb-c__bar")]


def _text(node: Any) -> str:
    """The text an element holds."""
    if isinstance(node, list):
        return "".join(_text(child) for child in node)
    if isinstance(node, dict):
        return _text(node["props"].get("children"))
    return "" if node is None else str(node)


def _point(period: str, value: float, kind: str | None = None, label: str | None = None) -> Any:
    """A bar's point; a fiscal year's has no ``kind``."""
    point: dict[str, Any] = {"period": period, "value": value}
    if kind is not None:
        point["kind"] = kind
    if label is not None:
        point["label"] = label
    return point


TRAILING = "12 months to 30 Sep 2026"
ESTIMATE = "Fiscal {}, the analysts' estimate"
SERIES = [
    _point("2023", 90),
    _point("2024", 100),
    _point("2025", 120),
    _point("ttm", 130, "trailing", TRAILING),
    _point("2026E", 150, "estimate", ESTIMATE.format(2026)),
    _point("2027E", 170, "estimate", ESTIMATE.format(2027)),
]


def _left(bar: dict[str, Any]) -> float:
    """A bar's left edge, where its path starts."""
    return float(bar["props"]["d"].split(",")[0].removeprefix("M"))


def test_a_trailing_and_an_estimate_bar_take_their_classes() -> None:
    assert _bars(_draw(series=SERIES)) == [
        "fb-c__bar",
        "fb-c__bar",
        "fb-c__bar",
        "fb-c__bar fb-c__bar--trailing",
        "fb-c__bar fb-c__bar--estimate",
        "fb-c__bar fb-c__bar--estimate",
    ]
    signed = [_point("2023", -90), *SERIES[1:]]
    assert _bars(_draw(series=signed)) == [
        "fb-c__bar fb-c__bar--neg",
        "fb-c__bar fb-c__bar--pos",
        "fb-c__bar fb-c__bar--pos",
        "fb-c__bar fb-c__bar--pos fb-c__bar--trailing",
        "fb-c__bar fb-c__bar--pos fb-c__bar--estimate",
        "fb-c__bar fb-c__bar--pos fb-c__bar--estimate",
    ]


def test_the_value_stands_on_the_last_bar_that_is_not_an_estimate() -> None:
    tree = _draw(series=SERIES)
    [value] = _classed(tree, "fb-c__capvalue")
    assert _text(value) == "130"
    bars = _classed(tree, "fb-c__bar")
    assert _left(bars[3]) < value["props"]["x"] < _left(bars[4])
    untrailed = [p for p in SERIES if p.get("kind") != "trailing"]
    tree = _draw(series=untrailed)
    [value] = _classed(tree, "fb-c__capvalue")
    assert _text(value) == "120"
    bars = _classed(tree, "fb-c__bar")
    assert _left(bars[2]) < value["props"]["x"] < _left(bars[3])


def test_a_chart_of_estimates_alone_prints_no_value_and_one_bar_draws() -> None:
    """Review Focus 5: a chart whose every point is an estimate draws its outlines and prints no
    figure; a chart of one fiscal year draws its one bar with its value on it."""
    estimates = [p for p in SERIES if p.get("kind") == "estimate"]
    tree = _draw(series=estimates)
    assert _bars(tree) == ["fb-c__bar fb-c__bar--estimate"] * 2
    assert _classed(tree, "fb-c__capvalue") == []
    tree = _draw(series=[_point("2025", 120)])
    assert _bars(tree) == ["fb-c__bar"]
    [value] = _classed(tree, "fb-c__capvalue")
    assert _text(value) == "120"


def test_an_estimate_below_zero_keeps_the_sign_s_class() -> None:
    """Review Focus 5: on a signed series an estimate's outline takes the colour its fill would
    have had, so it keeps the sign's class, as the trailing bar keeps its own beside the grey's;
    the value stands on the trailing bar. Under `inverse` the sign's classes swap as for any bar."""
    series = [
        _point("2024", 10),
        _point("ttm", -2, "trailing", TRAILING),
        _point("2026E", -3, "estimate", ESTIMATE.format(2026)),
        _point("2027E", 4, "estimate", ESTIMATE.format(2027)),
    ]
    tree = _draw(series=series)
    assert _bars(tree) == [
        "fb-c__bar fb-c__bar--pos",
        "fb-c__bar fb-c__bar--neg fb-c__bar--trailing",
        "fb-c__bar fb-c__bar--neg fb-c__bar--estimate",
        "fb-c__bar fb-c__bar--pos fb-c__bar--estimate",
    ]
    [value] = _classed(tree, "fb-c__capvalue")
    assert _text(value) == "-2"
    assert _bars(_draw(series=series, inverse=True))[2] == (
        "fb-c__bar fb-c__bar--pos fb-c__bar--estimate"
    )


def test_the_accessible_name_reads_what_the_bars_run_by() -> None:
    def name(tree: Any) -> str:
        [svg] = [e for e in _elements(tree) if e.get("type") == "svg"]
        return str(svg["props"]["aria-label"])

    assert name(_draw(series=SERIES, by="quarter")) == "Revenue by quarter"
    assert name(_draw(series=SERIES, by="period")) == "Revenue by period"
    assert name(_draw(series=SERIES)) == "Revenue by fiscal year"


def test_the_table_twin_reads_the_label() -> None:
    """A point without a label keeps its period, a stale year its mark; no table without
    ``tableView``."""
    series = [{**SERIES[0], "freshness": "aging"}, *SERIES[1:]]
    [table] = _classed(_draw(series=series, tableView=True), "fb-c__table")
    rows = [e for e in _elements(table) if e.get("type") == "tr"][1:]
    assert [_text(row["props"]["children"][0][0]) for row in rows] == [
        "2023!",
        "2024",
        "2025",
        TRAILING,
        ESTIMATE.format(2026),
        ESTIMATE.format(2027),
    ]
    assert _classed(_draw(series=series), "fb-c__table") == []
