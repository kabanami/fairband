"""The guidance records (spec 2026-11-06 Tier 2, 9; ``method.md`` 14.9): a figure the company gave
on a call for a future period, its midpoint and, for a fiscal-year revenue or EPS figure with its
actual of the year before on file, its step computed by the store; a newer record for the same metric
and period supersedes the older, and every record stays."""

import re
import sqlite3
from datetime import UTC, date, datetime

import pytest

from fairband.store.guidance import (
    BASES,
    METRICS,
    GuidanceRow,
    guidance_for,
    guidance_row,
    insert_guidance,
    year_before,
)
from fairband.store.ledger import Writer

NOW = datetime(2026, 11, 7, 9, 30, tzinfo=UTC)
CALL = date(2026, 10, 28)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
SAID = "We expect revenue of $1.1 billion to $1.3 billion for fiscal 2026."
SOURCE = "response:12/0/content"


def _add(
    conn: sqlite3.Connection,
    metric: str,
    period: str,
    low: float,
    high: float,
    base: float | None,
    symbol: str = "AAPL",
    basis: str = "gaap",
    call: date = CALL,
) -> int:
    return insert_guidance(
        conn, symbol, metric, period, low, high, basis, call, SAID, SOURCE, AGENT, NOW, base
    )


def _revenue(conn: sqlite3.Connection, low: float, high: float, base: float | None) -> int:
    return _add(conn, "revenue", "2026", low, high, base, symbol="aapl")


def test_a_range_takes_the_midpoint_and_the_step(conn: sqlite3.Connection) -> None:
    found = _revenue(conn, 1_100.0, 1_300.0, 1_000.0)
    row = guidance_row(conn, found)
    assert row is not None and row.step == pytest.approx(0.2)
    assert row == GuidanceRow(
        id=found,
        symbol="AAPL",
        metric="revenue",
        period="2026",
        low=1_100.0,
        high=1_300.0,
        midpoint=1_200.0,
        step=row.step,
        basis="gaap",
        as_of=CALL,
        text=SAID,
        source=SOURCE,
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        created_at=NOW,
        superseded_by=None,
    )
    assert guidance_row(conn, found + 1) is None


def test_a_point_has_equal_ends(conn: sqlite3.Connection) -> None:
    row = guidance_row(conn, _revenue(conn, 1_250.0, 1_250.0, 1_000.0))
    assert row is not None
    assert (row.low, row.high, row.midpoint) == (1_250.0, 1_250.0, 1_250.0)
    assert row.step == pytest.approx(0.25)


def test_a_step_needs_a_fiscal_year_revenue_or_eps_and_a_positive_base(
    conn: sqlite3.Connection,
) -> None:
    """No base on file, a base at or below zero, a quarter, or a metric that is not revenue or EPS:
    no step. The midpoint stands on every one."""
    margin = _add(conn, "operating_margin", "2026", 0.30, 0.32, 0.28)
    unstepped = (
        _revenue(conn, 1_100.0, 1_300.0, None),
        margin,
        _add(conn, "eps", "2026Q3", 1.5, 1.6, 1.4),
        _add(conn, "eps", "2027", 0.5, 0.7, -0.2),
        _add(conn, "eps", "2028", 0.5, 0.7, 0.0),
    )
    for record_id in unstepped:
        row = guidance_row(conn, record_id)
        assert row is not None and row.step is None, record_id
    row = guidance_row(conn, margin)
    assert row is not None and row.midpoint == pytest.approx(0.31)
    eps = guidance_row(conn, _add(conn, "eps", "2029", 6.3, 6.6, 6.0))
    assert eps is not None and eps.step == pytest.approx(0.075)
    assert year_before("revenue", "2026") == year_before("eps", "2026") == 2025
    assert year_before("eps", "2026Q3") is None and year_before("capex", "2026") is None


def test_a_newer_record_supersedes_the_older(conn: sqlite3.Connection) -> None:
    """Same metric and period: the old one's ``superseded_by`` is the new id, both listed newest
    first; another period, metric or company is left as it was."""
    first = _revenue(conn, 1_100.0, 1_300.0, 1_000.0)
    other_year = _add(conn, "revenue", "2027", 1_400.0, 1_500.0, None)
    other_metric = _add(conn, "capex", "2026", 90.0, 110.0, None)
    theirs = _add(conn, "revenue", "2026", 10.0, 12.0, None, symbol="AAL")
    second = _revenue(conn, 1_200.0, 1_300.0, 1_000.0)
    listed = guidance_for(conn, "aapl")
    assert [g.id for g in listed] == [second, other_metric, other_year, first]
    by_id = {g.id: g for g in listed}
    assert by_id[first].superseded_by == second
    assert [by_id[i].superseded_by for i in (second, other_year, other_metric)] == [None] * 3
    theirs_row = guidance_row(conn, theirs)
    assert theirs_row is not None and theirs_row.superseded_by is None
    third = _revenue(conn, 1_250.0, 1_250.0, 1_000.0)
    by_id = {g.id: g for g in guidance_for(conn, "AAPL")}
    assert (by_id[third].superseded_by, by_id[second].superseded_by) == (None, third)
    assert by_id[first].superseded_by == second  # the first keeps its successor


def test_a_gaap_and_an_adjusted_record_of_one_call_both_stay_current(
    conn: sqlite3.Connection,
) -> None:
    """The superseding key is the metric, the period and the basis: a call that guides GAAP and
    adjusted EPS gives two current records; a later GAAP figure supersedes the GAAP one alone."""
    gaap = _add(conn, "eps", "2027", 6.0, 6.4, None)
    adjusted = _add(conn, "eps", "2027", 7.0, 7.4, None, basis="adjusted")
    assert [g.superseded_by for g in guidance_for(conn, "AAPL")] == [None, None]
    later = _add(conn, "eps", "2027", 6.2, 6.4, None, call=date(2027, 1, 27))
    by_id = {g.id: g for g in guidance_for(conn, "AAPL")}
    assert by_id[gaap].superseded_by == later
    assert by_id[adjusted].superseded_by is None and by_id[later].superseded_by is None


def test_an_earlier_call_recorded_later_is_stored_superseded(conn: sqlite3.Connection) -> None:
    """The call's date orders the records, not the write: the previous call's figure recorded
    after the newest call's is stored already superseded by it, and the newest stays current; a
    record of the same call's date supersedes as a later one does."""
    newest = _add(conn, "revenue", "2027", 1_400.0, 1_500.0, None, call=date(2026, 10, 28))
    previous = _add(conn, "revenue", "2027", 1_300.0, 1_450.0, None, call=date(2026, 7, 29))
    by_id = {g.id: g for g in guidance_for(conn, "AAPL")}
    assert (by_id[newest].superseded_by, by_id[previous].superseded_by) == (None, newest)
    restated = _add(conn, "revenue", "2027", 1_420.0, 1_500.0, None, call=date(2026, 10, 28))
    by_id = {g.id: g for g in guidance_for(conn, "AAPL")}
    assert by_id[newest].superseded_by == restated and by_id[restated].superseded_by is None
    assert by_id[previous].superseded_by == newest  # kept as stored


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [
        (
            {"metric": "ebitda"},
            (
                "metric is one of revenue, eps, operating_margin, free_cash_flow, capex,"
                " revenue_growth or eps_growth"
            ),
        ),
        ({"period": "FY2026"}, "period is a fiscal year or a quarter (2026, 2026Q3)"),
        ({"period": "2026Q5"}, "period is a fiscal year or a quarter (2026, 2026Q3)"),
        ({"period": "2026-Q3"}, "period is a fiscal year or a quarter (2026, 2026Q3)"),
        ({"low": 1_400.0}, "low is above high"),
        ({"high": float("inf")}, "low and high are finite numbers"),
        ({"basis": "non-gaap"}, "basis is one of gaap, adjusted or constant-currency"),
        ({"text": " "}, "a guidance record needs its text"),
        ({"source": ""}, "a guidance record needs its source"),
    ],
)
def test_a_bad_value_is_refused_and_stores_nothing(
    conn: sqlite3.Connection, changes: dict[str, str | float], refusal: str
) -> None:
    given: dict[str, str | float] = {
        "metric": "revenue",
        "period": "2026",
        "low": 1_100.0,
        "high": 1_300.0,
        "basis": "gaap",
        "text": SAID,
        "source": SOURCE,
    } | changes
    with pytest.raises(ValueError, match=f"^{re.escape(refusal)}$"):
        insert_guidance(
            conn,
            "AAPL",
            str(given["metric"]),
            str(given["period"]),
            float(given["low"]),
            float(given["high"]),
            str(given["basis"]),
            CALL,
            str(given["text"]),
            str(given["source"]),
            AGENT,
            NOW,
            1_000.0,
        )
    assert guidance_for(conn, "AAPL") == []


def test_the_metrics_and_bases() -> None:
    assert METRICS == (
        "revenue",
        "eps",
        "operating_margin",
        "free_cash_flow",
        "capex",
        "revenue_growth",
        "eps_growth",
    )
    assert BASES == ("gaap", "adjusted", "constant-currency")
