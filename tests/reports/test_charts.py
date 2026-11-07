"""The chart tables (spec 2026-11-06 Tier 2, 13.6): the table twin of each chart the report page
draws, as the Markdown export carries it, every figure as a cite of it reads. On the ``snapshots``
fixture of ``conftest.py``: AAPL with ACME's synthetic statements (revenue $2,100 m in fiscal 2025,
$2,000 m in 2024)."""

import json
import sqlite3
from datetime import UTC, date, datetime
from typing import Any

from refresh.synthetic import NOW

from fairband.engine.secondary import Drivers, Part, secondary_value
from fairband.engine.sensitivity import SensitivityGrid
from fairband.policy import Policy
from fairband.reports.charts import ChartTable, chart_tables, shift_words
from fairband.reports.check import HEADINGS, headings, shown
from fairband.reports.tables import financial_tables
from fairband.store.ledger import Writer
from fairband.store.multiples import log_multiples
from fairband.store.reports import ReportRow, insert_report, report_row
from fairband.store.secondary import insert_secondary
from fairband.store.sensitivities import insert_sensitivity
from fairband.store.vendor import record_response

AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
EVIDENCE = [{"kind": "filing", "ref": "10-K", "note": None}]


def _report(
    conn: sqlite3.Connection,
    sid: int,
    cites: list[dict[str, Any]] | None = None,
    secondary_id: int | None = None,
) -> ReportRow:
    """AAPL's full report on snapshot ``sid``, its Valuation section citing ``cites``."""
    sections = [{"heading": h, "parts": ["Plain words."]} for h in headings("full report")]
    sections[7] = {"heading": "Valuation", "parts": ["The grid: ", *(cites or [])]}
    report_id = insert_report(
        conn,
        "AAPL",
        "full report",
        "hold",
        sections,
        None,
        sid,
        None,
        secondary_id,
        None,
        AGENT,
        NOW,
    )
    found = report_row(conn, report_id)
    assert found is not None
    return found


def _secondary(conn: sqlite3.Connection, policy: Policy, sid: int, form: str) -> int:
    """Spec 20.4's drivers (a terminal growth of 2%), or spec 20.1's one-part path."""
    if form == "drivers":
        drivers = Drivers(3, (0.10, 0.08, 0.05), (0.20, 0.20, 0.20), 0.25, 2.0, 0.02)
        valuation = secondary_value(
            drivers=drivers,
            revenue_0=1000.0,
            roic_t=0.12,
            debt=200.0,
            cash=100.0,
            shares=50.0,
            price=150.0,
            moat="Wide",
            policy=policy,
        )
        parts: tuple[Part, ...] = ()
    else:
        parts = (Part("the business", (100.0, 105.0, 110.25, 115.7625, 121.550625), 0.03, None),)
        valuation = secondary_value(
            parts=parts,
            debt=200.0,
            cash=100.0,
            shares=100.0,
            price=150.0,
            moat="Wide",
            policy=policy,
        )
    return insert_secondary(
        conn,
        "AAPL",
        sid,
        parts,
        valuation,
        "a second view",
        EVIDENCE,
        "agent",
        "agent",
        policy.version,
        policy.settings_hash,
        None,
        AGENT,
        NOW,
        revenue_0=1000.0 if form == "drivers" else None,
        roic_t=0.12 if form == "drivers" else None,
    )


def test_the_charts_lead_three_sections(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    tables = chart_tables(conn, _report(conn, snapshots["AAPL"]), policy)
    assert list(tables) == [HEADINGS[3], "Valuation", "Price and multiples"]


def test_section_4_holds_the_six_tables_at_the_cite_rounding(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """One table for each of the six financial tables, titled by it, over the last five fiscal
    years, each row by its name as the spec writes it; each cell written as a cite of it reads,
    an empty cell for a figure not on file."""
    financial = chart_tables(conn, _report(conn, snapshots["AAPL"]), policy)[HEADINGS[3]]
    assert [t.title for t in financial] == [
        "Growth and profitability",
        "Cash flow",
        "Balance sheet and solvency",
        "Returns on capital",
        "Capital allocation",
        "Quality scores",
    ]
    years = ("2021", "2022", "2023", "2024", "2025")
    assert {t.header for t in financial} == {("Fiscal year", *years)}
    growth = {row[0]: row[1:] for row in financial[0].rows}
    assert list(growth) == [
        "Revenue",
        "Revenue growth",
        "Gross margin",
        "Operating margin",
        "Net margin",
        "EPS",
    ]
    assert growth["Revenue"][-2:] == ("$2,000,000,000", "$2,100,000,000")
    assert growth["Revenue growth"][-1] == "5.0%"
    assert [row[0] for row in financial[3].rows] == [
        "ROIC",
        "ROE",
        "Ten-year aggregate ROIC",
        "Hurdle rate",
    ]
    quality = {row[0]: row[1:] for row in financial[5].rows}
    assert list(quality) == ["Altman's Z″", "Piotroski's F", "Beneish's M"]
    assert quality["Beneish's M"] == ("",) * 5  # not on file
    for table, chart in zip(financial_tables(conn, "AAPL", policy), financial, strict=True):
        for row, cells in zip(table.rows, chart.rows, strict=True):
            written = tuple("" if c.value is None else shown(c.value, c.unit) for c in row.cells)
            assert cells[1:] == written, (table.name, row.name)


def test_section_4_without_statements_has_tables_without_rows(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sections = [{"heading": h, "parts": ["Plain words."]} for h in headings("full report")]
    aal = snapshots["AAL"]
    report_id = insert_report(
        conn, "AAL", "full report", "avoid", sections, None, aal, None, None, None, AGENT, NOW
    )
    report = report_row(conn, report_id)
    assert report is not None
    financial = chart_tables(conn, report, policy)[HEADINGS[3]]
    assert len(financial) == 6 and all(t.rows == () for t in financial)


def test_section_8_holds_the_cited_sensitivity_readings_and_the_secondary_grid(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The readings the report cites, each once in the order first cited, a refused cell empty;
    then the grid of the secondary valuation the report rests on, its rows the terminal
    growths."""
    sid = snapshots["AAPL"]
    numbers = SensitivityGrid(
        (0.05, 0.08), (0.10, 0.20, 0.30), ((120.5, None, 140.0), (125.0, 133.37, 150.0)), (2, 2)
    )
    belief = insert_sensitivity(
        conn, "AAPL", sid, None, "growth.belief", "return.runway", numbers, "v", "h", AGENT, NOW
    )
    words = SensitivityGrid(("Narrow", "Wide"), (0.05,), ((110.0,), (130.0,)), None)
    moat = insert_sensitivity(
        conn, "AAPL", sid, None, "moat.class", "growth.belief", words, "v", "h", AGENT, NOW
    )
    insert_sensitivity(  # not cited: not shown
        conn, "AAPL", sid, None, "growth.belief", "return.runway", numbers, "v", "h", AGENT, NOW
    )
    cites = [
        {"cite": "$140", "ref": f"sensitivity:{moat}/2/1"},
        {"cite": "$120.50", "ref": f"sensitivity:{belief}/1/1"},
        {"cite": "$140.00", "ref": f"sensitivity:{belief}/1/3"},
    ]
    secondary = _secondary(conn, policy, sid, "drivers")
    valuation = chart_tables(conn, _report(conn, sid, cites, secondary), policy)["Valuation"]
    assert [t.title for t in valuation] == [
        f"Sensitivity {moat}: the moat by the belief",
        f"Sensitivity {belief}: the belief by the runway return",
        f"The grid of secondary valuation {secondary}",
    ]
    assert valuation[0] == ChartTable(
        f"Sensitivity {moat}: the moat by the belief",
        ("moat", "belief 5.0%"),
        (("Narrow", "$110.00"), ("Wide", "$130.00")),
    )
    assert valuation[1].header == (
        "belief",
        "runway return 10.0%",
        "runway return 20.0%",
        "runway return 30.0%",
    )
    assert valuation[1].rows == (
        ("5.0%", "$120.50", "", "$140.00"),
        ("8.0%", "$125.00", "$133.37", "$150.00"),
    )
    grid = valuation[2]
    assert grid.header == ("Terminal growth", "r 8.0%", "r 9.0%", "r 10.0%")
    assert [row[0] for row in grid.rows] == ["1.0%", "2.0%", "3.0%"]
    assert (grid.rows[0][1], grid.rows[1][2]) == ("$44.22", "$39.89")  # spec 20.4's corner, value
    assert chart_tables(conn, _report(conn, sid), policy)["Valuation"] == ()


def test_a_parts_grid_reads_its_rows_as_shifts(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    secondary = _secondary(conn, policy, sid, "parts")
    [grid] = chart_tables(conn, _report(conn, sid, secondary_id=secondary), policy)["Valuation"]
    assert grid.header == ("Every part's terminal growth", "r 8.0%", "r 9.0%", "r 10.0%")
    # spec 20.1's part is at g_T, so the top row lifts it nothing, and says so
    assert [row[0] for row in grid.rows] == ["−1 pp", "0 pp", "+0 pp, capped at g_T"]
    assert grid.rows[1][2] == "$16.82"  # spec 20.1's value a share
    assert shift_words(0.01, top=True) == "+1 pp"
    assert shift_words(0.005, top=True) == "+0.5 pp, capped at g_T"
    assert (shift_words(-0.01), shift_words(0.0), shift_words(0.01)) == ("−1 pp", "0 pp", "+1 pp")


def test_section_9_holds_the_statistics_and_the_year_end_points(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The four statistics of each P/E series over its ten years, with the day it began written as
    the references write a day; and each series' last point in each calendar year of the ten
    years (2016-10-29 falls before them), read from the store."""
    sid = snapshots["AAPL"]
    stats, year_end = chart_tables(conn, _report(conn, sid), policy)["Price and multiples"]
    assert (stats.title, year_end.title) == (
        "The P/E over ten years",
        "The P/E at the last point of each year of the ten years",
    )
    assert stats.rows == (("trailing P/E", "", "", "", "", ""), ("forward P/E", "", "", "", "", ""))
    assert year_end.rows == ()
    rows = [
        ["2016-10-29", 30.0, 30.0, 30.0, 30.0],  # a day before the ten years
        ["2016-10-30", 20.0, 20.0, 20.0, 20.0],
        ["2016-12-30", 18.0, 18.0, 18.0, 18.0],
        ["2021-06-30", "At Loss", 0, 0, 0],
        ["2025-12-31", 22.0, 22.0, 22.0, 22.0],
        ["2026-10-29", 23.0, 23.0, 23.0, 23.0],
        ["2026-10-30", 24.0, 24.0, 24.0, 24.0],
    ]
    at = datetime(2026, 11, 1, tzinfo=UTC)
    payload = json.dumps(rows)
    record_response(conn, "gf", "pettm", {"symbol": "AAPL"}, "AAPL", 200, payload, None, at)
    for day, pe_forward in (("2025-12-30", 21.0), ("2026-10-29", 21.5), ("2026-10-31", 22.5)):
        log_multiples(
            conn, "AAPL", date.fromisoformat(day), 150.0, None, None, pe_forward, 1, 1, at
        )
    stats, year_end = chart_tables(conn, _report(conn, sid), policy)["Price and multiples"]
    assert stats.header == ("Series", "Ten-year average", "Median", "High", "Low", "Since")
    assert stats.rows == (
        ("trailing P/E", "21.40x", "22.00x", "24.00x", "18.00x", "29 Oct 2016"),
        ("forward P/E", "21.67x", "21.50x", "22.50x", "21.00x", "30 Dec 2025"),
    )
    assert year_end.header == ("Year", "Trailing P/E", "Forward P/E")
    assert year_end.rows == (
        ("2016", "18.00x", ""),
        ("2025", "22.00x", "21.00x"),
        ("2026", "24.00x", "22.50x"),
    )
