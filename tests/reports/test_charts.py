"""The chart tables (spec 2026-11-06 Tier 2, 13.6): the table twin of each chart the report page
draws, as the Markdown export carries it, every figure as a cite of it reads. On the ``snapshots``
fixture of ``conftest.py``: AAPL with ACME's synthetic statements (revenue $2,100 m in fiscal 2025,
$2,000 m in 2024) and its closes, valued and priced 30 Oct 2026."""

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from refresh.synthetic import NOW, bodies
from support.engine_companies import fx_inputs, universe_deciles
from support.payloads import store_payloads
from support.web import TODAY

from fairband.engine.route import value_company
from fairband.engine.secondary import Drivers, Part, secondary_value
from fairband.engine.sensitivity import SensitivityGrid
from fairband.engine.types import Levels
from fairband.policy import Policy
from fairband.reports.charts import (
    BAND_TITLE,
    ChartTable,
    chart_tables,
    reading_axes,
    shift_words,
)
from fairband.reports.check import HEADINGS, headings, shown
from fairband.reports.tables import financial_tables
from fairband.store.ledger import Writer
from fairband.store.multiples import log_multiples
from fairband.store.reports import ReportRow, insert_report, report_row
from fairband.store.secondary import insert_secondary
from fairband.store.sensitivities import insert_sensitivity, sensitivity_row
from fairband.store.snapshots import insert_snapshot, snapshot_row
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


def test_a_company_in_another_currency_names_its_code_on_its_figures(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-10 7.4 on FXCO, the company in SEK: the financial tables' totals and figures a
    share are in the statements' currency, written with its code; a sensitivity reading's money
    axis is in it too (an override's unit, 7.3), while its cells are US dollars a share, as the
    value is; a percentage axis and a USD reading read as before."""
    aapl = snapshot_row(conn, snapshots["AAPL"])
    assert aapl is not None
    sid = insert_snapshot(
        conn, value_company(fx_inputs(), universe_deciles(), policy, TODAY), aapl.refresh_id
    )
    statements = {e: p for e, p in bodies(currency="SEK").items() if e != "earnings"}
    store_payloads(conn, "FXCO", statements, NOW)
    grid = SensitivityGrid((40.0, 80.0), (0.08,), ((110.0,), (115.25,)), None)
    reading = insert_sensitivity(
        conn, "FXCO", sid, None, "value.outside", "growth.belief", grid, "v", "h", AGENT, NOW
    )
    sections = [{"heading": h, "parts": ["Plain words."]} for h in headings("full report")]
    sections[7] = {
        "heading": "Valuation",
        "parts": [{"cite": "$110", "ref": f"sensitivity:{reading}/1/1"}],
    }
    report_id = insert_report(
        conn, "FXCO", "full report", "hold", sections, None, sid, None, None, None, AGENT, NOW
    )
    report = report_row(conn, report_id)
    assert report is not None
    tables = chart_tables(conn, report, policy)
    growth = {row[0]: row[1:] for row in tables[HEADINGS[3]][0].rows}
    assert growth["Revenue"][-2:] == ("SEK 2,000,000,000", "SEK 2,100,000,000")
    assert growth["Revenue growth"][-1] == "5.0%"
    assert growth["EPS"][-1].startswith("SEK ") and "$" not in growth["EPS"][-1]
    (valuation,) = tables["Valuation"]
    assert valuation.header == ("outside the business", "belief 8.0%")
    assert valuation.rows == (("SEK 40.00", "$110.00"), ("SEK 80.00", "$115.25"))
    found = sensitivity_row(conn, reading)
    assert found is not None
    assert reading_axes(found, "SEK").rows == ("SEK 40.00", "SEK 80.00")
    assert reading_axes(found, "USD").rows == ("$40.00", "$80.00")


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
    band, stats, year_end = chart_tables(conn, _report(conn, sid), policy)["Price and multiples"]
    assert (band.title, stats.title, year_end.title) == (
        BAND_TITLE,
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
    _, stats, year_end = chart_tables(conn, _report(conn, sid), policy)["Price and multiples"]
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


def test_section_9_leads_with_the_price_against_the_band_by_quarter(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The price chart's twin: each calendar quarter's last close of the five years to the newest
    close, with the fair band in force at the quarter's end, the newest snapshot priced on or
    before it (the later of two priced on one day); none before the first snapshot, and none on a
    refusal's."""
    sid = snapshots["AAPL"]
    first = snapshot_row(conn, sid)
    assert first is not None and first.fair_low is not None and first.fair_high is not None
    closes = [  # newest first, as FMP sends them
        {"symbol": "AAPL", "date": "2026-10-30", "close": 150.0},
        {"symbol": "AAPL", "date": "2026-10-01", "close": 155.0},  # not the quarter's last
        {"symbol": "AAPL", "date": "2025-11-03", "close": 190.0},
        {"symbol": "AAPL", "date": "2024-06-28", "close": 180.0},
        {"symbol": "AAPL", "date": "2021-11-01", "close": 140.0},
        {"symbol": "AAPL", "date": "2021-10-29", "close": 130.0},  # before the five years
    ]
    store_payloads(conn, "AAPL", {"price-history": closes}, datetime(2026, 11, 2, tzinfo=UTC))
    valued, refresh_id = first.result, first.refresh_id
    june = Levels(buy=150.0, fair_low=170.0, fair_high=210.0, trim=240.0)
    # priced after Q2 2024's last close and before its end: in force at the end
    insert_snapshot(conn, replace(valued, levels=june, price_date=date(2024, 6, 29)), refresh_id)
    november = replace(valued, levels=june, price_date=date(2025, 11, 3))
    insert_snapshot(conn, november, refresh_id)
    refused = replace(
        november, value=None, levels=None, price_to_value=None, designation=None, refusal="no"
    )
    insert_snapshot(conn, refused, refresh_id)  # the later of the day's two: a refusal
    band = chart_tables(conn, _report(conn, sid), policy)["Price and multiples"][0]
    assert band.title == BAND_TITLE == "The price against the band by quarter"
    assert band.header == ("Quarter", "Price", "Band low", "Band high")
    assert band.rows == (
        ("Q4 2021", "$140.00", "", ""),  # before the first snapshot
        ("Q2 2024", "$180.00", "$170.00", "$210.00"),
        ("Q4 2025", "$190.00", "", ""),  # the refusal in force
        ("Q4 2026", "$150.00", shown(first.fair_low, "price"), shown(first.fair_high, "price")),
    )
