"""The published reports and their judgments (spec 2026-11-06 Tier 2, 12 and 13.1): revisions
count up per company; the sections and the judgments read back as written."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fairband.store.inbox import Mode
from fairband.store.ledger import OWNER, Writer
from fairband.store.overrides import insert_override
from fairband.store.reports import (
    JudgmentRow,
    ReportRow,
    insert_judgments,
    insert_report,
    judgments_for,
    latest_judgments,
    latest_report,
    latest_reports,
    report_row,
    reports_for,
)

NOW = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
SECTIONS = [
    {
        "heading": "Summary",
        "parts": ["The price of ", {"cite": "$150.00", "ref": "snapshot:4/price"}],
    },
    {"heading": "The business", "parts": ["Phones."]},
]
JUDGMENT = {"judgment": "moat", "bull": "patents", "bear": "lapse", "decision": "Wide"}


def _report(
    conn: sqlite3.Connection,
    symbol: str,
    mode: Mode = "full report",
    *,
    reuses_full_report_of: int | None = None,
    review_id: int | None = None,
    secondary_id: int | None = None,
    work_item_id: int | None = None,
    writer: Writer = AGENT,
    at: datetime = NOW,
) -> int:
    """A report of ``symbol`` on snapshot 4."""
    return insert_report(
        conn,
        symbol,
        mode,
        "buy",
        SECTIONS,
        reuses_full_report_of,
        4,
        review_id,
        secondary_id,
        work_item_id,
        writer,
        at,
    )


def test_revisions_count_up_per_symbol(conn: sqlite3.Connection) -> None:
    first = _report(conn, "AAPL")
    other = _report(conn, "MSFT", at=NOW + timedelta(minutes=1))
    second = _report(
        conn,
        "AAPL",
        "valuation review",
        reuses_full_report_of=first,
        review_id=7,
        secondary_id=8,
        work_item_id=9,
        writer=OWNER,
        at=NOW + timedelta(minutes=2),
    )
    assert [r.revision for r in reports_for(conn, "AAPL")] == [2, 1]
    assert report_row(conn, other) == ReportRow(
        id=other,
        symbol="MSFT",
        revision=1,
        mode="full report",
        stance="buy",
        sections=tuple(SECTIONS),
        reuses_full_report_of=None,
        snapshot_id=4,
        review_id=None,
        secondary_id=None,
        work_item_id=None,
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        created_at=NOW + timedelta(minutes=1),
    )
    latest = latest_report(conn, "AAPL")
    assert latest is not None and latest.id == second
    assert (latest.mode, latest.reuses_full_report_of, latest.principal, latest.actor) == (
        "valuation review",
        first,
        "owner",
        None,
    )
    assert (latest.review_id, latest.secondary_id, latest.work_item_id) == (7, 8, 9)
    assert {s: r.id for s, r in latest_reports(conn).items()} == {"AAPL": second, "MSFT": other}
    assert latest_report(conn, "AAL") is None and report_row(conn, 99) is None


def test_judgments_round_trip(conn: sqlite3.Connection) -> None:
    override_id = insert_override(
        conn,
        "AAPL",
        "moat.class",
        "Wide",
        "Narrow",
        "class",
        "the patents lapse",
        [{"kind": "filing", "ref": "10-K", "note": None}],
        "lasting",
        None,
        None,
        4,
        AGENT,
        NOW,
        "applied",
        "",
    )
    first = _report(conn, "AAPL")
    ids = insert_judgments(
        conn,
        first,
        "AAPL",
        [
            {"judgment": "phase", "bull": "growing", "bear": "slowing", "decision": "as is"},
            JUDGMENT | {"override_id": override_id},
        ],
    )
    assert judgments_for(conn, first) == [
        JudgmentRow(ids[0], first, "AAPL", "phase", "growing", "slowing", "as is", None),
        JudgmentRow(ids[1], first, "AAPL", "moat", "patents", "lapse", "Wide", override_id),
    ]
    assert latest_judgments(conn, "AAPL") == judgments_for(conn, first)
    second = _report(conn, "AAPL")
    assert latest_judgments(conn, "AAPL") == [] and latest_judgments(conn, "AAL") == []
    with pytest.raises(KeyError):  # another company's override
        insert_judgments(conn, second, "MSFT", [JUDGMENT | {"override_id": override_id}])
    assert judgments_for(conn, second) == []
