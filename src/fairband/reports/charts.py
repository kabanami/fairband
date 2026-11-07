"""The chart tables of a report (spec 2026-11-06 Tier 2, 13.6 and 18.4; ``method.md`` 16.6):
where the report page draws a chart, the Markdown export carries its table twin under the
section's heading, before the prose, and the page titles its charts with the words here, so the
two never differ. Every figure is written as a cite of it would read (``check.shown``), a day as
the references write it (``refs.day_words``, "3 Nov 2026"), and a cell with no figure on file is
empty.

``chart_tables`` reads them from the store at export, no vendor called, by the heading of the
section each leads:

- "Financial performance and health": the six tables of ``tables.financial_tables``, one each,
  titled by the table (``TITLES``), each row by its name in words (``row_name``, "Altman's Z″",
  "Ten-year aggregate ROIC"), over the last five fiscal years; a table without statements has no
  rows. The page draws a part's charts under its table's title, each titled by its row's name.
- "Valuation": each sensitivity reading the sections cite (a ``sensitivity:`` ref), once, in the
  order first cited, titled and its axes worded by ``reading_axes``, which the reading's read
  sends the page: the rows the first input's values and the columns the second's; then the grid
  of the secondary valuation the report rests on (``GRID_TITLE``), its columns the rates and its
  rows the terminal growths or, on the parts form, the shift in every part's
  (``store.secondary.GRID_ROWS``, ``grid_row_words``, which Appendix A's grid carries for the
  page). None when the report cites no reading and rests on no secondary valuation with a grid.
- "Price and multiples": the price against the band by quarter (``BAND_TITLE``): each calendar
  quarter's last close of the ``BAND_YEARS`` years to the newest close on file
  (``inputs.stored_closes``, as the price-history read serves them), with the fair band in force
  at the quarter's end, the newest snapshot priced on or before it (``snapshots.band_points``, as
  the band-history read serves them), empty before the first snapshot and on a refusal's; then the
  four statistics of the trailing and the forward P/E over their ten years with the day each
  series began (``reports.multiples``), and each series' last point in each calendar year of the
  ten years, a column a series titled as the page's chart of it (``SERIES_TITLES``).
"""

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from fairband.engine.overrides import LABELS, TAGS
from fairband.engine.types import Levels
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.refresh.inputs import stored_closes
from fairband.reports.check import parts, shown
from fairband.reports.multiples import SERIES, STATS, Series, stored_series, years_before
from fairband.reports.refs import day_words, field_words, unit_of
from fairband.reports.tables import Table, financial_tables
from fairband.store.reports import ReportRow
from fairband.store.secondary import GRID_ROWS, secondary_row
from fairband.store.sensitivities import SensitivityRow, sensitivity_row
from fairband.store.snapshots import BandPoint, band_points

TITLES = {
    "growth": "Growth and profitability",
    "cash_flow": "Cash flow",
    "solvency": "Balance sheet and solvency",
    "returns": "Returns on capital",
    "capital_allocation": "Capital allocation",
    "quality": "Quality scores",
}
# The page's two multiples charts, titled as the year-end table's columns.
SERIES_TITLES = {"pe": "Trailing P/E", "pe_forward": "Forward P/E"}
GRID_TITLE = "The grid of secondary valuation {}"
BAND_TITLE = "The price against the band by quarter"
BAND_YEARS = 5
_QUARTER_ENDS = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
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


@dataclass(frozen=True)
class ReadingAxes:
    """A sensitivity reading's table title and its axes in words: each input's label and each of
    its values as a cite of it reads."""

    title: str
    row_label: str
    col_label: str
    rows: tuple[str, ...]
    cols: tuple[str, ...]


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
        "Price and multiples": (_band(conn, symbol), *_multiples(conn, symbol)),
    }


def reading_axes(reading: SensitivityRow) -> ReadingAxes:
    """The reading's table title, "Sensitivity 7: the belief by the runway return", and its axes:
    each input's label and its values as a cite of them reads, a word as it is."""
    row_label = _LABELS.get(reading.row_tag, reading.row_tag)
    col_label = _LABELS.get(reading.col_tag, reading.col_tag)
    return ReadingAxes(
        f"Sensitivity {reading.id}: the {row_label} by the {col_label}",
        row_label,
        col_label,
        tuple(_input(v, reading.row_tag) for v in reading.row_values),
        tuple(_input(v, reading.col_tag) for v in reading.col_values),
    )


def grid_row_words(rows: Sequence[float], shifts: bool) -> tuple[str, ...]:
    """A secondary valuation's grid rows in words: the terminal growths as percentages, or on the
    parts form the shifts (``shift_words``), the third the top one."""
    return tuple(
        shift_words(g, top=i == 2) if shifts else shown(g, "percent") for i, g in enumerate(rows)
    )


def shift_words(x: float, *, top: bool = False) -> str:
    """A shift in every part's terminal growth in points: "−1 pp", "0 pp", "+1 pp". The ``top``
    row, the rise each part takes up to g_T, carries its sign whatever its size and, below a
    point, says the cap held it: "+0 pp, capped at g_T", "+0.5 pp, capped at g_T"."""
    points = round(x * 100, 1)
    size = f"{abs(points):g} pp"
    if top:
        return f"+{size}" + (", capped at g_T" if points < 1 else "")
    return f"{'−' if points < 0 else '+' if points > 0 else ''}{size}"


def _financial(table: Table) -> ChartTable:
    """A financial table titled by its name, a row a line in words, a column a fiscal year; no
    rows without statements."""
    periods = tuple(cell.period for cell in table.rows[0].cells) if table.rows else ()
    if not periods:
        return ChartTable(TITLES[table.name], ("Fiscal year",), ())
    rows = tuple(
        (row_name(row.name), *(_shown(cell.value, cell.unit) for cell in row.cells))
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
    axes = reading_axes(reading)
    header = (axes.row_label, *(f"{axes.col_label} {word}" for word in axes.cols))
    rows = tuple(
        (word, *(_shown(cell, "per-share") for cell in cells))
        for word, cells in zip(axes.rows, reading.cells, strict=True)
    )
    return ChartTable(axes.title, header, rows)


def _secondary_grid(conn: sqlite3.Connection, report: ReportRow) -> list[ChartTable]:
    """The grid of the secondary valuation the report rests on; none without one."""
    secondary = None if report.secondary_id is None else secondary_row(conn, report.secondary_id)
    grid: Mapping[str, Any] | None = None if secondary is None else secondary.grid
    if secondary is None or grid is None:
        return []
    shifts = GRID_ROWS[secondary.form] == "shifts"
    corner = "Every part's terminal growth" if shifts else "Terminal growth"
    rows = tuple(
        (word, *(_shown(cell, "per-share") for cell in cells))
        for word, cells in zip(grid_row_words(grid["rows"], shifts), grid["cells"], strict=True)
    )
    header = (corner, *(f"r {shown(rate, 'percent')}" for rate in grid["cols"]))
    return [ChartTable(GRID_TITLE.format(secondary.id), header, rows)]


def _band(conn: sqlite3.Connection, symbol: str) -> ChartTable:
    """Each calendar quarter's last close of the five years to the newest, with the fair band in
    force at the quarter's end; empty before the first snapshot and on a refusal's."""
    closes = stored_closes(conn, symbol)
    since = years_before(closes[-1][0], BAND_YEARS) if closes else date.min
    last: dict[tuple[int, int], float] = {}
    for day, close in closes:  # oldest first: the quarter's last close wins
        if day >= since:
            last[day.year, (day.month - 1) // 3 + 1] = close
    points = band_points(conn, symbol)
    rows = []
    for (year, quarter), close in last.items():
        levels = _in_force(points, date(year, *_QUARTER_ENDS[quarter]))
        low, high = (None, None) if levels is None else (levels.fair_low, levels.fair_high)
        rows.append(
            (
                f"Q{quarter} {year}",
                shown(close, "per-share"),
                _shown(low, "per-share"),
                _shown(high, "per-share"),
            )
        )
    return ChartTable(BAND_TITLE, ("Quarter", "Price", "Band low", "Band high"), tuple(rows))


def _in_force(points: Sequence[BandPoint], day: date) -> Levels | None:
    """The levels of the newest point priced on or before ``day``; none before the first, and none
    when that point is a refusal's."""
    found = None
    for point in points:  # oldest first
        if point.day > day:
            break
        found = point
    return None if found is None else found.levels


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
            "The P/E at the last point of each year of the ten years",
            ("Year", *(SERIES_TITLES[name] for name in SERIES)),
            years,
        ),
    )


def row_name(name: str) -> str:
    """A table row's name in words, led by a capital: "Revenue growth", "Altman's Z″"."""
    words = field_words(name)
    return words[:1].upper() + words[1:]


def _input(value: float | str, tag: str) -> str:
    """An input's value as a cite of it reads; a word as it is."""
    return value if isinstance(value, str) else shown(value, _UNITS.get(tag))


def _shown(value: float | None, unit: str | None) -> str:
    """A figure as a cite of it reads; an empty cell for none on file."""
    return "" if value is None else shown(value, unit)
