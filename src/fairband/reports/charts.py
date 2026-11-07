"""The chart tables of a report (spec 2026-11-06 Tier 2, 13.6; ``method.md`` 16.6): where the
report page draws a chart, the Markdown export carries its table twin under the section's
heading, before the prose. Every figure is written as a cite of it would read
(``check.shown``), a day as the references write it (``refs.day_words``, "3 Nov 2026"), and a
cell with no figure on file is empty.

``chart_tables`` reads them from the store at export, no vendor called, by the heading of the
section each leads:

- "Financial performance and health": the six tables of ``tables.financial_tables``, one each,
  titled by the table (``TITLES``), each row by its name in words (``refs.field_words``, "Altman's
  Z″", "Ten-year aggregate ROIC"), over the last five fiscal years; a table without statements has
  no rows.
- "Valuation": each sensitivity reading the sections cite (a ``sensitivity:`` ref), once, in the
  order first cited, the rows the first input's values and the columns the second's; then the
  grid of the secondary valuation the report rests on, its columns the rates and its rows the
  terminal growths or, on the parts form, the shift in every part's (``store.secondary.GRID_ROWS``).
  None when the report cites no reading and rests on no secondary valuation with a grid.
- "Price and multiples": the four statistics of the trailing and the forward P/E over their ten
  years with the day each series began (``reports.multiples``), and each series' last point in
  each calendar year of the ten years.
"""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fairband.engine.overrides import LABELS, TAGS
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.reports.check import parts, shown
from fairband.reports.multiples import SERIES, STATS, Series, stored_series
from fairband.reports.refs import day_words, field_words, unit_of
from fairband.reports.tables import Table, financial_tables
from fairband.store.reports import ReportRow
from fairband.store.secondary import GRID_ROWS, secondary_row
from fairband.store.sensitivities import SensitivityRow, sensitivity_row

TITLES = {
    "growth": "Growth and profitability",
    "cash_flow": "Cash flow",
    "solvency": "Balance sheet and solvency",
    "returns": "Returns on capital",
    "capital_allocation": "Capital allocation",
    "quality": "Quality scores",
}
_SERIES_NAMES = {"pe": "trailing P/E", "pe_forward": "forward P/E"}
# Each input's label and unit by its tag as a stored reading names it.
_LABELS: dict[str, str] = {tag: label for tag, label in LABELS.items()}
_UNITS: dict[str, str | None] = {tag: unit_of(spec.unit) for tag, spec in TAGS.items()}


@dataclass(frozen=True)
class ChartTable:
    """A chart's table twin: its title, its header and its rows, every cell written."""

    title: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def chart_tables(
    conn: sqlite3.Connection, report: ReportRow, policy: Policy, tax: TaxTable | None = None
) -> dict[str, tuple[ChartTable, ...]]:
    """The report's chart tables by the heading of the section they lead (module docstring);
    ``policy`` is the effective one and ``tax`` the statements' table."""
    symbol = report.symbol
    return {
        "Financial performance and health": tuple(
            _financial(table) for table in financial_tables(conn, symbol, policy, tax)
        ),
        "Valuation": (*_sensitivities(conn, report), *_secondary_grid(conn, report)),
        "Price and multiples": _multiples(conn, symbol),
    }


def shift_words(x: float) -> str:
    """A shift in every part's terminal growth in points: "−1 pp", "0 pp", "+1 pp"."""
    points = round(x * 100)
    return f"{'−' if points < 0 else '+' if points > 0 else ''}{abs(points)} pp"


def _financial(table: Table) -> ChartTable:
    """A financial table titled by its name, a row a line in words, a column a fiscal year; no
    rows without statements."""
    periods = tuple(cell.period for cell in table.rows[0].cells) if table.rows else ()
    if not periods:
        return ChartTable(TITLES[table.name], ("Fiscal year",), ())
    rows = tuple(
        (_row_name(row.name), *(_shown(cell.value, cell.unit) for cell in row.cells))
        for row in table.rows
    )
    return ChartTable(TITLES[table.name], ("Fiscal year", *periods), rows)


def _sensitivities(conn: sqlite3.Connection, report: ReportRow) -> list[ChartTable]:
    """The sensitivity readings of the company the sections cite, once each, in cite order."""
    cited: list[int] = []
    for _, part in parts(report.sections):
        ref = str(part.get("ref", "")).strip() if isinstance(part, Mapping) else ""
        form, _, path = ref.partition(":")
        head = path.partition("/")[0]
        if form == "sensitivity" and head.isdecimal() and int(head) not in cited:
            cited.append(int(head))
    readings = (sensitivity_row(conn, reading_id) for reading_id in cited)
    return [_reading(r) for r in readings if r is not None and r.symbol == report.symbol]


def _reading(reading: SensitivityRow) -> ChartTable:
    row_label = _LABELS.get(reading.row_tag, reading.row_tag)
    col_label = _LABELS.get(reading.col_tag, reading.col_tag)
    header = (row_label, *(f"{col_label} {_input(v, reading.col_tag)}" for v in reading.col_values))
    rows = tuple(
        (_input(v, reading.row_tag), *(_shown(cell, "per-share") for cell in cells))
        for v, cells in zip(reading.row_values, reading.cells, strict=True)
    )
    title = f"Sensitivity {reading.id}: the {row_label} by the {col_label}"
    return ChartTable(title, header, rows)


def _secondary_grid(conn: sqlite3.Connection, report: ReportRow) -> list[ChartTable]:
    """The grid of the secondary valuation the report rests on; none without one."""
    secondary = None if report.secondary_id is None else secondary_row(conn, report.secondary_id)
    grid: Mapping[str, Any] | None = None if secondary is None else secondary.grid
    if secondary is None or grid is None:
        return []
    shifts = GRID_ROWS[secondary.form] == "shifts"
    corner = "Every part's terminal growth" if shifts else "Terminal growth"
    rows = tuple(
        (
            shift_words(g) if shifts else shown(g, "percent"),
            *(_shown(cell, "per-share") for cell in cells),
        )
        for g, cells in zip(grid["rows"], grid["cells"], strict=True)
    )
    header = (corner, *(f"r {shown(rate, 'percent')}" for rate in grid["cols"]))
    return [ChartTable(f"The grid of secondary valuation {secondary.id}", header, rows)]


def _multiples(conn: sqlite3.Connection, symbol: str) -> tuple[ChartTable, ChartTable]:
    """The two P/E series' statistics, and their last point in each calendar year of the ten."""
    series: dict[str, Series | None] = {name: stored_series(conn, symbol, name) for name in SERIES}
    stats = tuple(
        (
            _SERIES_NAMES[name],
            *(_shown(None if s is None else s.stats[stat], "multiple") for stat in STATS),
            "" if s is None or s.since is None else day_words(s.since),
        )
        for name, s in series.items()
    )
    header = ("Series", "Ten-year average", "Median", "High", "Low", "Since")
    year_end: dict[int, dict[str, float]] = {}
    for name, s in series.items():
        for day, value in () if s is None else s.points:  # oldest first: the year's last wins
            year_end.setdefault(day.year, {})[name] = value
    years = tuple(
        (str(year), *(_shown(year_end[year].get(name), "multiple") for name in SERIES))
        for year in sorted(year_end)
    )
    return (
        ChartTable("The P/E over ten years", header, stats),
        ChartTable(
            "The P/E on the last day of each year of the ten years",
            ("Year", "Trailing P/E", "Forward P/E"),
            years,
        ),
    )


def _row_name(name: str) -> str:
    """A table row's name in words, led by a capital: "Revenue growth", "Altman's Z″"."""
    words = field_words(name)
    return words[:1].upper() + words[1:]


def _input(value: float | str, tag: str) -> str:
    """An input's value as a cite of it reads; a word as it is."""
    return value if isinstance(value, str) else shown(value, _UNITS.get(tag))


def _shown(value: float | None, unit: str | None) -> str:
    """A figure as a cite of it reads; an empty cell for none on file."""
    return "" if value is None else shown(value, unit)
