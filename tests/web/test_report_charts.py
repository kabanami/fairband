"""The report's ROIC chart on a year whose average invested capital is at or below zero
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
``kindsLine`` the line under a chart with a bar that is not a fiscal year; ``groupCharts`` the
charts of Financial performance and health with those bars and that line, each group with its
title, and ``quarterCharts`` the last earnings call's three charts by quarter with theirs, the
export's titles. Their trees come back as the page's script builds them, a bundle component's
props unread by the stub.

And the company page's Research tab's charts (the Research tab's design, 7.4 rules 3, 4, 6 and 7,
and 7.9): ``groupCharts``, ``quarterCharts``, ``gridCharts`` and ``priceCharts`` give the report's
charts with no raised panel, the charts of a pair and of the quarters' row at a height of their
own, and a read the server refused as its sentence in the chart's place; on
``support.research_answers``' series of LFOX."""

from itertools import pairwise
from typing import Any

import pytest
from support import research_answers as answers
from support.page import NODE, STATIC, classed, elements, node, text

from fairband.reports.charts import QUARTERS_TITLE, TITLES
from fairband.reports.tables import ANALYSTS_BASIS

NOTE = "average invested capital is at or below zero"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _call(helper: str, *args: Any) -> Any:
    """What charts.js's ``helper`` returns on ``args``, through JSON."""
    return node(helper, list(args), STATIC / "charts.js")


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
    return node("Fairband.HistoryBars", [{"title": "Revenue", **props}])


def _bars(tree: Any) -> list[str]:
    """The bars' class lists, in order."""
    return [e["props"]["className"] for e in classed(tree, "fb-c__bar")]


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
    [value] = classed(tree, "fb-c__capvalue")
    assert text(value) == "130"
    bars = classed(tree, "fb-c__bar")
    assert _left(bars[3]) < value["props"]["x"] < _left(bars[4])
    untrailed = [p for p in SERIES if p.get("kind") != "trailing"]
    tree = _draw(series=untrailed)
    [value] = classed(tree, "fb-c__capvalue")
    assert text(value) == "120"
    bars = classed(tree, "fb-c__bar")
    assert _left(bars[2]) < value["props"]["x"] < _left(bars[3])


def test_a_chart_of_estimates_alone_prints_no_value_and_one_bar_draws() -> None:
    """Review Focus 5: a chart whose every point is an estimate draws its outlines and prints no
    figure; a chart of one fiscal year draws its one bar with its value on it."""
    estimates = [p for p in SERIES if p.get("kind") == "estimate"]
    tree = _draw(series=estimates)
    assert _bars(tree) == ["fb-c__bar fb-c__bar--estimate"] * 2
    assert classed(tree, "fb-c__capvalue") == []
    tree = _draw(series=[_point("2025", 120)])
    assert _bars(tree) == ["fb-c__bar"]
    [value] = classed(tree, "fb-c__capvalue")
    assert text(value) == "120"


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
    [value] = classed(tree, "fb-c__capvalue")
    assert text(value) == "-2"
    assert _bars(_draw(series=series, inverse=True))[2] == (
        "fb-c__bar fb-c__bar--pos fb-c__bar--estimate"
    )


def test_the_accessible_name_reads_what_the_bars_run_by() -> None:
    def name(tree: Any) -> str:
        [svg] = [e for e in elements(tree) if e.get("type") == "svg"]
        return str(svg["props"]["aria-label"])

    assert name(_draw(series=SERIES, by="quarter")) == "Revenue by quarter"
    assert name(_draw(series=SERIES, by="period")) == "Revenue by period"
    assert name(_draw(series=SERIES)) == "Revenue by fiscal year"


def test_the_table_twin_reads_the_label() -> None:
    """A point without a label keeps its period, a stale year its mark; no table without
    ``tableView``."""
    series = [{**SERIES[0], "freshness": "aging"}, *SERIES[1:]]
    [table] = classed(_draw(series=series, tableView=True), "fb-c__table")
    rows = [e for e in elements(table) if e.get("type") == "tr"][1:]
    assert [text(row["props"]["children"][0][0]) for row in rows] == [
        "2023!",
        "2024",
        "2025",
        TRAILING,
        ESTIMATE.format(2026),
        ESTIMATE.format(2027),
    ]
    assert classed(_draw(series=series), "fb-c__table") == []


def _axis(series: list[Any]) -> list[str]:
    """The ticks the bars' axis prints, in order."""
    [axis] = classed(_draw(series=series), "fb-c__xaxis")
    return [text(tick) for tick in classed(axis, "fb-c__tick")]


FISCAL = [_point(str(year), 100 + year % 10) for year in range(2021, 2026)]
TO_DATE = _point("to date", 130, "trailing", TRAILING)
AHEAD = [_point(f"{year}E", 150, "estimate", ESTIMATE.format(year)) for year in (2026, 2027, 2028)]


def test_the_axis_always_prints_the_trailing_twelve_months_tick() -> None:
    """Spec 2026-11-15 6.5, 6.6: on eight bars and on nine the axis prints every other tick, so
    the trailing twelve months' tick is kept as the two ends' are and a tick within a slot of it
    is dropped; on seven bars or fewer every tick prints, as before."""
    assert _axis([*FISCAL, TO_DATE, *AHEAD]) == ["2021", "2023", "to date", "2028E"]
    assert _axis([*FISCAL, TO_DATE, *AHEAD[:2]]) == ["2021", "2023", "to date", "2027E"]
    assert _axis([*FISCAL, TO_DATE, AHEAD[0]]) == [
        "2021",
        "2022",
        "2023",
        "2024",
        "2025",
        "to date",
        "2026E",
    ]


def _ticks_at(series: list[Any], width: int) -> list[str]:
    """The ticks the bars' axis prints, in order, on a chart ``width`` px wide."""
    [axis] = classed(_draw(series=series, width=width), "fb-c__xaxis")
    return [text(tick) for tick in classed(axis, "fb-c__tick")]


def test_a_narrow_chart_thins_its_year_ticks_so_none_runs_into_the_trailing_one() -> None:
    """The Research tab's design, 7.9 (the look after the whole-branch review's fixes): the
    design system's axis printed every tick of seven bars or fewer whatever the chart's width, so
    at the tab's 320px the last fiscal year's tick and "to date" ran into each other ("2026to
    date"). HistoryBars tells its axis how many ticks its plot holds, one to 70px, the room the
    last year's tick and "to date", anchored at its end, need side by side, seven at most and two
    at least: on a chart of 320px, 248px of plot, three, so of five fiscal years and the trailing
    twelve months it prints the first year, the third and "to date", and not the last fiscal
    year; at 418px, a pair's chart alone in its row at a 1,200px window, 346px of plot, four,
    still no tick in the slot before "to date" (at 56px a tick it printed all six there, and the
    two ran together); at 550px, as wide as the report page's, all six, as before, and at 560px.
    Nine bars with estimates at 320px print no two ticks in adjacent slots."""
    six = [*FISCAL, TO_DATE]
    assert _ticks_at(six, 320) == ["2021", "2023", "to date"]
    assert "2025" not in _ticks_at(six, 320)
    at_418 = _ticks_at(six, 418)
    assert at_418[0] == "2021" and at_418[-1] == "to date"
    assert "2025" not in at_418  # the slot before "to date"
    everything = ["2021", "2022", "2023", "2024", "2025", "to date"]
    assert _ticks_at(six, 550) == everything
    assert _ticks_at(six, 560) == everything
    nine = [*FISCAL, TO_DATE, *AHEAD]
    printed = _ticks_at(nine, 320)
    slots = [[p["period"] for p in nine].index(tick) for tick in printed]
    assert printed[0] == "2021" and "to date" in printed and printed[-1] == "2028E"
    assert all(b - a > 1 for a, b in pairwise(slots)), slots


def _xticks(component: str, width: int, series: list[Any]) -> list[tuple[str, float]]:
    """The ticks the axis of the bundle's ``component`` prints on ``series`` at ``width`` px, in
    order, each its words and where it stands."""
    tree = node("Fairband." + component, [{"title": "A chart", "series": series, "width": width}])
    [axis] = classed(tree, "fb-c__xaxis")
    return [(text(t), float(t["props"]["x"])) for t in classed(axis, "fb-c__tick")]


# 21 quarters, Q4 2021 to Q4 2026, the price against a band, as the Research tab's price chart
# draws five years of closes.
CLOSES = [
    {
        "period": f"Q{1 + (q + 3) % 4} {2021 + (q + 3) // 4}",
        "price": 100.0 + q,
        "fairLow": 90.0,
        "fairHigh": 120.0,
    }
    for q in range(21)
]
# Five years of ROIC against the hurdle rate, as the Research tab's ROIC chart draws them.
SPREAD = [{"period": str(2021 + k), "roic": 20.0 + k, "wacc": 9.0} for k in range(5)]


def test_the_band_chart_prints_as_many_quarter_ticks_as_its_width_holds() -> None:
    """The Research tab's design, 7.9: at a 1,440px window the Price and multiples column is
    about 372px wide, and the band chart printed seven quarter ticks into each other. Its axis
    now holds the ticks its plot's width holds, one to 64px, a quarter's tick being wider than a
    year's ("Q4 2021"), seven at most, two at least: at 372px (230px of plot) no more than three,
    the first and the last among them, none closer than 64px to the next; at 740px, the panel's
    width at a 2,000px window, the seven it printed before."""
    narrow = _xticks("BandHistory", 372, CLOSES)
    plot = 372 - 56 - 86
    assert len(narrow) <= plot // 64
    assert narrow[0][0] == "Q4 2021" and narrow[-1][0] == "Q4 2026"
    assert all(b[1] - a[1] >= 64 for a, b in pairwise(narrow)), narrow
    wide = [words for words, _ in _xticks("BandHistory", 740, CLOSES)]
    assert wide == [CLOSES[i]["period"] for i in (0, 3, 6, 9, 12, 15, 20)]


def test_the_roic_chart_prints_as_many_year_ticks_as_its_width_holds() -> None:
    """The Research tab's design, 7.9: SpreadChart's axis holds the ticks its plot's width
    holds, one to 56px as the bar chart's, seven at most: at 320px (186px of plot) no more than
    three, the first and the last among them; at 550px, about as wide as the report page drew
    it, all five, as before."""
    narrow = [words for words, _ in _xticks("SpreadChart", 320, SPREAD)]
    assert len(narrow) <= (320 - 56 - 78) // 56
    assert narrow[0] == "2021" and narrow[-1] == "2025"
    wide = [words for words, _ in _xticks("SpreadChart", 550, SPREAD)]
    assert wide == ["2021", "2022", "2023", "2024", "2025"]


def test_an_axis_with_no_trailing_point_prints_as_before() -> None:
    """The other charts pass no `kind`: eight bars of fiscal years and estimates, or eight
    quarters, print every other tick and the last, as before the patch."""
    assert _axis([*FISCAL, *AHEAD]) == ["2021", "2023", "2025", "2028E"]
    quarters = [_point(f"Q{q} {y}", 10) for y in (25, 26) for q in (1, 2, 3, 4)]
    assert _axis(quarters) == ["Q1 25", "Q3 25", "Q1 26", "Q4 26"]


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


def test_the_line_says_the_estimates_basis_where_their_points_carry_it() -> None:
    """The whole-branch review's I2: where the drawn estimate points carry their cells' note, the
    EPS's ``tables.ANALYSTS_BASIS``, the line's second sentence says it after a comma, in the
    cell's words; estimates without a note keep the short sentence."""
    trailing = {"period": "ttm", "kind": "trailing", "label": "12 months to 30 Sep 2026"}
    estimate = {"period": "2026E", "kind": "estimate", "label": "2026 estimate"}
    noted = {**estimate, "note": ANALYSTS_BASIS}
    assert _call("reportCharts.kindsLine", [trailing, noted, noted]) == (
        "Grey: the 12 months to 30 Sep 2026. Outlined: analysts' estimates, on the analysts' own"
        " basis, which can leave out items the reported EPS includes."
    )
    assert _call("reportCharts.kindsLine", [noted]) == (
        f"Outlined: analysts' estimates, {ANALYSTS_BASIS}."
    )
    assert _call("reportCharts.kindsLine", [estimate]) == "Outlined: analysts' estimates."


def test_a_point_carries_its_cell_s_note() -> None:
    """A cell's note rides on its point, so the line under the chart can read it; a cell with no
    note gives a point with none."""
    columns = [_column("2025"), _column("2026E")]
    row = {
        "name": "eps",
        "unit": "per-share",
        "cells": [
            {"period": "2025", "value": 5.5, "note": None},
            {"period": "2026E", "value": 6.0, "note": ANALYSTS_BASIS},
        ],
    }
    assert _call("reportCharts.points", row, columns) == [
        {"period": "2025", "value": 5.5, "label": "2025"},
        {
            "period": "2026E",
            "value": 6.0,
            "kind": "estimate",
            "label": "2026 estimate",
            "note": ANALYSTS_BASIS,
        },
    ]


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


def _groups(read: dict[str, Any]) -> list[Any]:
    """The charts ``groupCharts`` gives on the financial tables' read settled as ``read``, every
    group's in their order."""
    drawn: dict[str, dict[str, Any]] = _call("reportCharts.groupCharts", read)
    return [chart for group in drawn.values() for chart in group["charts"]]


def _quarters(read: dict[str, Any]) -> Any:
    """The charts by quarter ``quarterCharts`` gives on the read settled as ``read``; none on an
    answer without the quarters."""
    drawn = _call("reportCharts.quarterCharts", read)
    return None if drawn is None else drawn["charts"]


def _body(**over: Any) -> dict[str, Any]:
    """The read's body: the growth and capital allocation tables and the quarters."""
    body = {"symbol": "ACME", "currency": "USD", "tables": [GROWTH, CAPITAL], "quarters": QUARTERS}
    return body | over


def _panel(tree: Any, title: str) -> tuple[dict[str, Any] | None, list[str]]:
    """The place of the chart titled ``title`` among drawn charts, each with no panel of its own
    (``app-charts__chart``): the chart's props, none where it shows that nothing is on file, and
    the captions under it."""
    for panel in classed(tree, "app-charts__chart"):
        charts = [e["props"] for e in elements(panel) if "series" in e["props"]]
        heads = [text(e) for e in classed(panel, "fb-c__title")]
        if [c["title"] for c in charts] == [title] or heads == [title]:
            captions = [text(e) for e in classed(panel, "caption")]
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
    """A quarter's label stays whole for the tooltip; a period the store names otherwise, a
    half-year, takes its label, its year shortened, or the label as it is."""
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
    no label, the accessible name by fiscal year and no line under the chart; no charts by
    quarter."""
    row = GROWTH["rows"][0]
    assert _call("reportCharts.points", row) == [
        {"period": cell["period"], "value": cell["value"]} for cell in row["cells"]
    ]
    older = {k: v for k, v in GROWTH.items() if k != "columns"}
    body = {"symbol": "ACME", "currency": "USD", "tables": [older]}
    chart, captions = _panel(_groups({"body": body}), "Revenue")
    assert chart is not None and "by" not in chart
    assert all("kind" not in p and "label" not in p for p in chart["series"])
    assert captions == []
    assert _quarters({"body": body}) is None


def test_the_financial_charts_mark_the_trailing_and_the_estimate_bars() -> None:
    """Spec 2026-11-15 6.5, 6.6: a chart with a bar that is not a fiscal year runs by period and
    says which bar is which under it, once, from the columns of the bars it draws; buybacks and
    dividends, the page's sum of two rows, gets its trailing bar; a chart whose trailing cell
    holds no figure, the share count's change, draws its fiscal years alone, as before."""
    part = _groups({"body": _body()})
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
    unpaid = _table(
        "capital_allocation",
        ["2024", "2025", "ttm"],
        {"dividends": ("currency", [-10.0, -11.0, None]), "buybacks": ("currency", [-50.0] * 3)},
    )
    alone = _groups({"body": _body(tables=[GROWTH, unpaid])})
    returned, captions = _panel(alone, "Buybacks and dividends")
    assert returned is not None and "by" not in returned and captions == []
    assert _ticks(returned) == ["2024", "2025"]  # no trailing dividends, no trailing sum
    shares, captions = _panel(part, "Share count change")
    assert shares is not None and "by" not in shares and captions == []
    assert _ticks(shares) == ["2024", "2025"]
    for title in ("Revenue", "Operating margin", "EPS", "Buybacks and dividends"):
        chart, _ = _panel(part, title)
        assert chart is not None, title
        assert not any("Q" in tick for tick in _ticks(chart)), title  # never a quarter
    assert _panel(part, "Free cash flow") == (None, ["No data on file."])


def test_the_eps_chart_says_its_estimates_basis_under_it() -> None:
    """The whole-branch review's I2: the EPS row's estimate cells carry the analysts' basis as
    their note, so the line under the EPS chart says it; the revenue's carry none, and its line
    stays the short one."""
    noted = {
        **GROWTH,
        "rows": [
            r
            if r["name"] != "eps"
            else {
                **r,
                "cells": [
                    {**c, "note": ANALYSTS_BASIS} if c["period"].endswith("E") else c
                    for c in r["cells"]
                ],
            }
            for r in GROWTH["rows"]
        ],
    }
    part = _groups({"body": _body(tables=[noted, CAPITAL])})
    _, captions = _panel(part, "EPS")
    assert captions == [
        f"Grey: the 12 months to 30 Sep 2026. Outlined: analysts' estimates, {ANALYSTS_BASIS}."
    ]
    assert _panel(part, "Revenue")[1] == [LINE]


def test_the_last_earnings_call_draws_three_charts_by_quarter() -> None:
    """Spec 2026-11-15 6.5: the revenue, the operating margin and the EPS of the stored periods,
    titled by their rows' names and run by quarter, each tick the quarter short and each point
    its column's label; no line under them."""
    section = _quarters({"body": _body()})
    charts = [e["props"] for e in elements(section) if "series" in e["props"]]
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


def test_the_quarters_with_no_stored_period_say_nothing_is_on_file() -> None:
    """A company with no stored period: the quarters table has no column and its rows no cells,
    so its three charts show "No data on file.", as a financial table's do without statements."""
    rows: dict[str, tuple[str, list[float | None]]] = {
        "revenue": ("currency", []),
        "operating_margin": ("percent", []),
        "eps": ("per-share", []),
    }
    section = _quarters({"body": _body(quarters=_table("quarters", [], rows))})
    for title in ("Revenue", "Operating margin", "EPS"):
        assert _panel(section, title) == (None, ["No data on file."])


# ---------------------------------------------------------------- the Research tab's charts

SMALL = 120  # the charts' height in a pair and in the quarters' row (7.9)
GROUPS = ["growth", "cash_flow", "solvency", "returns", "capital_allocation", "quality"]
REFUSED = "no financial statements for LFOX"


def _charts(tree: Any) -> list[dict[str, Any]]:
    """The props of each chart drawn in ``tree``: a bundle chart's element, which carries its
    ``series`` or, a grid, its ``cells``."""
    return [e["props"] for e in elements(tree) if "series" in e["props"] or "cells" in e["props"]]


def test_group_charts_give_each_group_s_charts_at_the_height_asked_with_no_panel() -> None:
    """Rule 3: the six groups by their tables' names, each with its title, the export's
    (``charts.TITLES``), so the page and the Markdown never differ (7.9), and its charts, 3, 2,
    2, 1, 2 and 2, each the report's chart, HistoryBars or SpreadChart, at the height given, on no
    raised panel; with no height, the bundle's own."""
    drawn = _call("reportCharts.groupCharts", {"body": answers.TABLES}, SMALL)
    assert list(drawn) == GROUPS
    assert [drawn[key]["title"] for key in GROUPS] == [TITLES[key] for key in GROUPS]
    assert [TITLES[key] for key in GROUPS] == [
        "Growth and profitability",
        "Cash flow",
        "Balance sheet and solvency",
        "Returns on capital",
        "Capital allocation",
        "Quality scores",
    ]
    assert [len(drawn[key]["charts"]) for key in GROUPS] == [3, 2, 2, 1, 2, 2]
    titles = []
    for key in GROUPS:
        for chart in drawn[key]["charts"]:
            [props] = _charts(chart)
            assert props["height"] == SMALL
            titles.append(props["title"])
        assert classed(drawn[key]["charts"], "app-chart") == []
    assert titles == [
        "Revenue",
        "Operating margin",
        "EPS",
        "Free cash flow",
        "Stock compensation to revenue",
        "Net debt to EBITDA",
        "Interest coverage",
        "ROIC",
        "Buybacks and dividends",
        "Share count change",
        "Altman's Z″",
        "Piotroski's F",
    ]
    [roic] = _charts(drawn["returns"]["charts"])
    assert roic["subtitle"] == "against the hurdle rate"  # the SpreadChart
    whole = _call("reportCharts.groupCharts", {"body": answers.TABLES})
    assert all("height" not in props for key in GROUPS for props in _charts(whole[key]["charts"]))
    assert [whole[key]["title"] for key in GROUPS] == [TITLES[key] for key in GROUPS]


def test_group_charts_of_a_refused_read_give_its_sentence() -> None:
    drawn = _call("reportCharts.groupCharts", {"error": REFUSED}, SMALL)
    assert list(drawn) == ["refused"]
    assert text(drawn["refused"]) == f"The financial tables did not load: {REFUSED}."


def test_quarter_charts_give_the_three_charts_by_quarter() -> None:
    """Rule 4: the revenue, the operating margin and the EPS by quarter at the height given, with
    no panel, under the export's title for them (``charts.QUARTERS_TITLE``, 7.9); a refused read
    its sentence alone; an answer without the quarters none."""
    drawn = _call("reportCharts.quarterCharts", {"body": answers.TABLES}, SMALL)
    assert list(drawn) == ["title", "charts"]
    assert drawn["title"] == QUARTERS_TITLE == "By quarter"
    assert len(drawn["charts"]) == 3
    charts = [props for chart in drawn["charts"] for props in _charts(chart)]
    assert [c["title"] for c in charts] == ["Revenue", "Operating margin", "EPS"]
    assert all(c["by"] == "quarter" and c["height"] == SMALL for c in charts)
    assert classed(drawn["charts"], "app-chart") == []
    refused = _call("reportCharts.quarterCharts", {"error": REFUSED}, SMALL)
    assert list(refused) == ["refused"]
    assert text(refused["refused"]) == f"The figures by quarter did not load: {REFUSED}."
    older = {k: v for k, v in answers.TABLES.items() if k != "quarters"}
    assert _call("reportCharts.quarterCharts", {"body": older}, SMALL) is None


def _report(secondary: bool = False) -> dict[str, Any]:
    """The synthetic report, with the secondary valuation's grid where ``secondary``."""
    report: dict[str, Any] = answers.answer()["report"]
    if secondary:
        record = answers.RECORDS["secondaryValuations"][0]
        grid = record["grid"]
        report["appendixA"]["secondary"] = {
            "id": record["id"],
            "grid": {
                "rowWords": ["−1 pp", "0 pp", "+1 pp"],
                "cols": grid["cols"],
                "cells": grid["cells"],
                "rowsAre": grid["rowsAre"],
            },
        }
    return report


def test_grid_charts_give_each_reading_and_the_secondary_grid_a_failed_one_its_sentence() -> None:
    """Rule 6: each reading's grid in its order, a reading that failed its sentence in its place,
    then the secondary valuation's grid; on no raised panel; none for a report with neither."""
    readings = [{"error": "no sensitivity reading 8"}, {"body": answers.READING}]
    drawn = _call("reportCharts.gridCharts", _report(secondary=True), readings)
    assert len(drawn) == 3
    assert text(drawn[0]) == "A sensitivity reading did not load: no sensitivity reading 8."
    assert _charts(drawn[0]) == []
    [reading] = _charts(drawn[1])
    assert reading["title"] == answers.READING["title"]
    assert reading["basis"] == "reviewed"  # the report rests on review 6
    assert reading["current"] == {"row": 1, "col": 1}
    [grid] = _charts(drawn[2])
    assert grid["title"] == "The grid of secondary valuation 5"
    assert classed(drawn, "app-chart") == []
    assert _call("reportCharts.gridCharts", _report(), []) == []


def test_price_charts_give_the_band_and_the_two_p_e_or_a_refusal_in_their_place() -> None:
    """Rule 7: the price against the band, the trailing P/E and the forward P/E, on no raised
    panel; with the multiples history refused, the band and the sentence; each once its reads
    have landed."""
    landed = {
        "closes": {"body": answers.CLOSES},
        "band": {"body": answers.BAND},
        "multiples": {"body": answers.MULTIPLES},
    }
    drawn = _call("reportCharts.priceCharts", landed)
    assert [[c["title"] for c in _charts(chart)] for chart in drawn] == [
        ["The price against the band by quarter"],
        ["Trailing P/E"],
        ["Forward P/E"],
    ]
    assert classed(drawn, "app-chart") == []
    refused = _call(
        "reportCharts.priceCharts", landed | {"multiples": {"error": "GuruFocus refused"}}
    )
    assert len(refused) == 2
    assert [c["title"] for c in _charts(refused[0])] == ["The price against the band by quarter"]
    assert text(refused[1]) == "The P/E history did not load: GuruFocus refused."
    assert _call("reportCharts.priceCharts", {"closes": landed["closes"]}) == []
    alone = _call("reportCharts.priceCharts", {"multiples": landed["multiples"]})
    assert [[c["title"] for c in _charts(chart)] for chart in alone] == [
        ["Trailing P/E"],
        ["Forward P/E"],
    ]
