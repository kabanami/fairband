"""The report page's ROIC chart on a year whose average invested capital is at or below zero
(B-8, the founder's ruling of 2026-11-15; method 16.6): the year's figure has the wrong sign and
no meaning, so the chart leaves it out and a line under it names the years and why. charts.js
runs in node after the bundle and app.js (``page.mjs``), and the test reads what its
``roicPoints`` makes of the returns table's two rows.

And the bundle's ``HistoryBars`` on a bar that is not a fiscal year (spec 2026-11-15 6.6): the
trailing twelve months in the de-emphasis grey, an analysts' estimate an outline, the value on
the last bar that is not an estimate, the accessible name by what the bars run by and the table
twin by each point's label. The harness calls the component with its props and the tests read
the tree it draws.

And the page's charts past the fiscal year and by quarter (spec 2026-11-15 6.5, 6.6): charts.js's
``points`` makes a point of each cell under its column, its tick, its kind and its label;
``kindsLine`` the line under a chart with a bar that is not a fiscal year; ``draw`` section 4's
charts with those bars and that line, and section 5's three charts by quarter. ``draw``'s tree
comes back as the page's script builds it, a bundle component's props unread by the stub."""

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


def test_a_chart_s_points_carry_each_column_s_kind_and_label() -> None:
    columns = [
        {"period": "2025", "kind": "fiscal", "label": "2025"},
        {"period": "ttm", "kind": "trailing", "label": "12 months to 30 Sep 2026"},
        {"period": "2026E", "kind": "estimate", "label": "2026 estimate"},
    ]
    row = {
        "name": "revenue",
        "unit": "currency",
        "cells": [
            {"period": "2025", "value": 2100.0},
            {"period": "ttm", "value": 1300.0},
            {"period": "2026E", "value": 2200.0},
        ],
    }
    assert _call("reportCharts.points", row, columns) == [
        {"period": "2025", "value": 2100.0, "label": "2025"},
        {
            "period": "to date",
            "value": 1300.0,
            "kind": "trailing",
            "label": "12 months to 30 Sep 2026",
        },
        {"period": "2026E", "value": 2200.0, "kind": "estimate", "label": "2026 estimate"},
    ]


def test_the_line_under_a_chart_names_the_grey_and_the_outlined_bars() -> None:
    trailing = {"period": "ttm", "kind": "trailing", "label": "12 months to 30 Sep 2026"}
    estimate = {"period": "2026E", "kind": "estimate", "label": "2026 estimate"}
    fiscal = {"period": "2025", "kind": "fiscal", "label": "2025"}
    assert _call("reportCharts.kindsLine", [fiscal, trailing, estimate]) == (
        "Grey: the 12 months to 30 Sep 2026. Outlined: analysts' estimates."
    )
    assert _call("reportCharts.kindsLine", [fiscal, trailing]) == (
        "Grey: the 12 months to 30 Sep 2026."
    )
    assert _call("reportCharts.kindsLine", [fiscal, estimate]) == "Outlined: analysts' estimates."
    assert _call("reportCharts.kindsLine", [fiscal]) is None


def _column(period: str) -> dict[str, str]:
    """A column as the financial tables' read serves it, by its period (spec 2026-11-15 6.1,
    6.4)."""
    if period == "ttm":
        return {"period": period, "kind": "trailing", "label": TRAILING}
    if period.endswith("E"):
        return {"period": period, "kind": "estimate", "label": f"{period[:-1]} estimate"}
    if "-" in period:
        year, quarter = period.split("-")
        return {"period": period, "kind": "quarter", "label": f"{quarter} {year}"}
    return {"period": period, "kind": "fiscal", "label": period}


def _table(
    name: str, periods: list[str], rows: dict[str, tuple[str, list[float | None]]]
) -> dict[str, Any]:
    """A table as the read serves it: its columns, and each row a cell under each column."""
    return {
        "name": name,
        "columns": [_column(period) for period in periods],
        "rows": [
            {
                "name": row,
                "unit": unit,
                "cells": [
                    {
                        "period": period,
                        "value": value,
                        "unit": unit,
                        "ref": f"table:ACME/{name}/{row}/{period}",
                        "note": None,
                    }
                    for period, value in zip(periods, values, strict=True)
                ],
            }
            for row, (unit, values) in rows.items()
        ],
    }


GROWTH = _table(
    "growth",
    ["2024", "2025", "ttm", "2026E", "2027E"],
    {
        "revenue": ("currency", [1900.0, 2100.0, 2150.0, 2200.0, 2400.0]),
        "operating_margin": ("percent", [0.30, 0.31, 0.32, None, None]),
        "eps": ("per-share", [5.0, 5.5, 5.6, 6.0, 6.5]),
    },
)
CAPITAL = _table(
    "capital_allocation",
    ["2024", "2025", "ttm"],
    {
        "dividends": ("currency", [-10.0, -11.0, -12.0]),
        "buybacks": ("currency", [-50.0, -60.0, -70.0]),
        "share_count_change": ("percent", [-0.02, -0.03, None]),
    },
)
QUARTERS = _table(
    "quarters",
    ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"],
    {
        "revenue": ("currency", [500.0, 520.0, 530.0, 600.0]),
        "operating_margin": ("percent", [0.30, 0.31, None, 0.33]),
        "eps": ("per-share", [1.3, 1.4, 1.5, 1.6]),
    },
)
LINE = "Grey: the 12 months to 30 Sep 2026. Outlined: analysts' estimates."


def _sections(read: dict[str, Any]) -> Any:
    """``draw``'s charts by the heading, on the financial tables' read settled as ``read``."""
    return _call("reportCharts.draw", {}, {"tables": read}, False)


def _body(**over: Any) -> dict[str, Any]:
    """The read's body: the growth and capital allocation tables and the quarters."""
    body = {"symbol": "ACME", "currency": "USD", "tables": [GROWTH, CAPITAL], "quarters": QUARTERS}
    return body | over


def _panel(tree: Any, title: str) -> tuple[dict[str, Any] | None, list[str]]:
    """The panel of the chart titled ``title`` in a drawn section: the chart's props, none where
    the panel shows that nothing is on file, and the captions in the panel."""
    for panel in _classed(tree, "app-chart"):
        charts = [e["props"] for e in _elements(panel) if "series" in e["props"]]
        heads = [_text(e) for e in _classed(panel, "fb-c__title")]
        if [c["title"] for c in charts] == [title] or heads == [title]:
            captions = [_text(e) for e in _classed(panel, "caption")]
            return (charts[0] if charts else None), captions
    raise AssertionError(title)


def _ticks(chart: dict[str, Any]) -> list[str]:
    """The ticks under a chart's bars, in order."""
    return [p["period"] for p in chart["series"]]


def test_a_cell_with_no_value_is_left_out_and_shifts_no_kind() -> None:
    periods = ["2024", "2025", "ttm", "2026E", "2027E"]
    row = _table("growth", periods, {"eps": ("per-share", [None, 5.5, None, 6.0, 6.5])})
    columns = [_column(period) for period in periods]
    assert _call("reportCharts.points", row["rows"][0], columns) == [
        {"period": "2025", "value": 5.5, "label": "2025"},
        {"period": "2026E", "value": 6.0, "kind": "estimate", "label": "2026 estimate"},
        {"period": "2027E", "value": 6.5, "kind": "estimate", "label": "2027 estimate"},
    ]


def test_a_quarter_s_tick_is_its_quarter_and_its_year_s_last_two_digits() -> None:
    """A quarter's label stays whole for the tooltip and the table twin; a period the store names
    otherwise, a half-year, takes its label, its year shortened, or the label as it is."""
    half = {"period": "2026-H1", "kind": "quarter", "label": "H1 2026"}
    odd = {"period": "2026-P1", "kind": "quarter", "label": "first period"}
    periods = ["2026-Q3", "2026-H1", "2026-P1"]
    row = _table("quarters", periods, {"revenue": ("currency", [600.0, 1100.0, 900.0])})
    assert _call("reportCharts.points", row["rows"][0], [_column("2026-Q3"), half, odd]) == [
        {"period": "Q3 26", "value": 600.0, "label": "Q3 2026"},
        {"period": "H1 26", "value": 1100.0, "label": "H1 2026"},
        {"period": "first period", "value": 900.0, "label": "first period"},
    ]


def test_a_table_served_without_columns_draws_its_cells_as_today() -> None:
    """A page loaded against an older answer: the points from the cells' own periods, no kind and
    no label, the accessible name by fiscal year and no line under the chart; no section 5."""
    row = GROWTH["rows"][0]
    assert _call("reportCharts.points", row) == [
        {"period": cell["period"], "value": cell["value"]} for cell in row["cells"]
    ]
    older = {k: v for k, v in GROWTH.items() if k != "columns"}
    sections = _sections({"body": {"symbol": "ACME", "currency": "USD", "tables": [older]}})
    chart, captions = _panel(sections["Financial performance and health"], "Revenue")
    assert chart is not None and "by" not in chart
    assert all("kind" not in p and "label" not in p for p in chart["series"])
    assert captions == []
    assert sections["The last earnings call"] is None


def test_section_4_draws_the_trailing_and_the_estimate_bars_with_the_line_under() -> None:
    """Spec 2026-11-15 6.5, 6.6: a chart with a bar that is not a fiscal year runs by period and
    says which bar is which under it, once, from the columns of the bars it draws; buybacks and
    dividends, the page's sum of two rows, gets its trailing bar; a chart whose trailing cell
    holds no figure, the share count's change, draws its fiscal years alone, as before."""
    part = _sections({"body": _body()})["Financial performance and health"]
    revenue, captions = _panel(part, "Revenue")
    assert revenue is not None and revenue["by"] == "period"
    assert _ticks(revenue) == ["2024", "2025", "to date", "2026E", "2027E"]
    kinds = [p.get("kind") for p in revenue["series"]]
    assert kinds == [None, None, "trailing", "estimate", "estimate"]
    assert captions == [LINE]
    margin, captions = _panel(part, "Operating margin")
    assert margin is not None and margin["by"] == "period"
    assert _ticks(margin) == ["2024", "2025", "to date"]
    assert captions == ["Grey: the 12 months to 30 Sep 2026."]
    returned, captions = _panel(part, "Buybacks and dividends")
    assert returned is not None and returned["by"] == "period"
    drawn = [(p["period"], p["value"]) for p in returned["series"]]
    assert drawn == [("2024", 60), ("2025", 71), ("to date", 82)]
    assert returned["series"][-1]["kind"] == "trailing"
    assert captions == ["Grey: the 12 months to 30 Sep 2026."]
    shares, captions = _panel(part, "Share count change")
    assert shares is not None and "by" not in shares and captions == []
    assert _ticks(shares) == ["2024", "2025"]
    for title in ("Revenue", "Operating margin", "EPS", "Buybacks and dividends"):
        chart, _ = _panel(part, title)
        assert chart is not None, title
        assert not any("Q" in tick for tick in _ticks(chart)), title  # never a quarter
    assert _panel(part, "Free cash flow") == (None, ["No data on file."])


def test_section_5_draws_three_charts_by_quarter() -> None:
    """Spec 2026-11-15 6.5: under the export's title for its table, "By quarter", the revenue, the
    operating margin and the EPS of the stored periods, titled by their rows' names and run by
    quarter, each tick the quarter short and each point its column's label; no line under them."""
    section = _sections({"body": _body()})["The last earnings call"]
    assert [_text(e) for e in _elements(section) if e.get("type") == "h5"] == ["By quarter"]
    charts = [e["props"] for e in _elements(section) if "series" in e["props"]]
    assert [c["title"] for c in charts] == ["Revenue", "Operating margin", "EPS"]
    for chart in charts:
        assert chart["by"] == "quarter"
        assert all("kind" not in p for p in chart["series"])
        assert _panel(section, chart["title"])[1] == []
    revenue, margin, eps = charts
    assert _ticks(revenue) == ["Q4 25", "Q1 26", "Q2 26", "Q3 26"]
    assert [p["label"] for p in revenue["series"]] == ["Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026"]
    assert revenue["unit"] == "USD" and eps["unit"] == "USD a share"
    assert _ticks(margin) == ["Q4 25", "Q1 26", "Q3 26"]  # a gap, never a zero


def test_section_5_with_no_stored_period_says_nothing_is_on_file() -> None:
    """A company with no stored period: the quarters table has no column and its rows no cells,
    so the section shows its three panels with "No data on file.", as section 4 does for a table
    without statements."""
    rows: dict[str, tuple[str, list[float | None]]] = {
        "revenue": ("currency", []),
        "operating_margin": ("percent", []),
        "eps": ("per-share", []),
    }
    section = _sections({"body": _body(quarters=_table("quarters", [], rows))})
    for title in ("Revenue", "Operating margin", "EPS"):
        assert _panel(section["The last earnings call"], title) == (None, ["No data on file."])


def test_section_5_says_why_when_the_read_was_refused() -> None:
    sections = _sections({"error": "no financial statements for ACME"})
    assert _text(sections["The last earnings call"]) == (
        "The figures by quarter did not load: no financial statements for ACME."
    )
    assert _text(sections["Financial performance and health"]) == (
        "The financial tables did not load: no financial statements for ACME."
    )
