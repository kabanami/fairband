"""The research records: notes, findings, kill criteria and news items (spec 2026-11-06 Tier 2,
section 9), each with its writer and read newest first."""

import re
import sqlite3
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from fairband.store.ledger import OWNER, Writer
from fairband.store.overrides import insert_override
from fairband.store.research import (
    AlreadyInState,
    FindingRow,
    KillCriterionRow,
    NewsItemRow,
    NoteRow,
    add_finding,
    add_kill_criterion,
    add_news_item,
    add_note,
    finding_row,
    findings_for,
    kill_criteria_for,
    kill_criterion_row,
    news_items_for,
    notes_for,
    set_kill_criterion,
)

NOW = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
BY_AGENT = {"principal": "agent", "actor": "claude-opus-5-5", "client": "claude-code/2.1"}
BY_OWNER = {"principal": "owner", "actor": None, "client": None}
FILING = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": "the segment table"}


def _override(conn: sqlite3.Connection, symbol: str) -> int:
    """An applied override of ``symbol``."""
    return insert_override(
        conn,
        symbol,
        "margin.target",
        None,
        0.3,
        "ratio",
        "r",
        [FILING],
        "lasting",
        None,
        None,
        1,
        AGENT,
        NOW,
        "applied",
        "",
    )


def test_notes(conn: sqlite3.Connection) -> None:
    override_id = _override(conn, "AAPL")
    first = add_note(conn, "aapl", "margins look peaked", OWNER, NOW)
    other = add_note(conn, "MSFT", "not this one", OWNER, NOW)
    second = add_note(conn, "AAPL", "the override's source", AGENT, LATER, override_id=override_id)
    assert not conn.in_transaction
    assert notes_for(conn, "AAPL") == [
        NoteRow(
            id=second,
            symbol="AAPL",
            text="the override's source",
            **BY_AGENT,
            at=LATER,
            override_id=override_id,
        ),
        NoteRow(
            id=first,
            symbol="AAPL",
            text="margins look peaked",
            **BY_OWNER,
            at=NOW,
            override_id=None,
        ),
    ]
    assert [n.id for n in notes_for(conn, "MSFT")] == [other]
    with pytest.raises(ValueError, match="^a note needs text$"):
        add_note(conn, "AAPL", "  ", OWNER, NOW)


def test_a_note_carries_only_the_companys_override(conn: sqlite3.Connection) -> None:
    other = _override(conn, "MSFT")
    for override_id in (99, other):  # none, or another company's
        with pytest.raises(KeyError):
            add_note(conn, "AAPL", "the source", AGENT, NOW, override_id=override_id)
    assert notes_for(conn, "AAPL") == []
    assert not conn.in_transaction


def test_findings(conn: sqlite3.Connection) -> None:
    first = add_finding(
        conn,
        "AAPL",
        date(2025, 9, 27),
        "services grew 11.2%",
        FILING,
        AGENT,
        NOW,
        value=0.112,
        unit="percent",
        period="2025",
    )
    bare = {"kind": "url", "ref": "https://example.com/q3"}
    second = add_finding(conn, "AAPL", date(2026, 7, 31), "a new plant", bare, OWNER, LATER)
    assert findings_for(conn, "AAPL") == [
        FindingRow(
            id=second,
            symbol="AAPL",
            as_of=date(2026, 7, 31),
            text="a new plant",
            source_kind="url",
            source_ref="https://example.com/q3",
            source_note=None,
            value=None,
            unit=None,
            period=None,
            **BY_OWNER,
            at=LATER,
        ),
        FindingRow(
            id=first,
            symbol="AAPL",
            as_of=date(2025, 9, 27),
            text="services grew 11.2%",
            source_kind="filing",
            source_ref="10-K 2025, p. 41",
            source_note="the segment table",
            value=0.112,
            unit="percent",
            period="2025",
            **BY_AGENT,
            at=NOW,
        ),
    ]
    assert finding_row(conn, first) == findings_for(conn, "AAPL")[1]
    assert finding_row(conn, 99) is None
    assert findings_for(conn, "MSFT") == []


KINDS = "filing, transcript, url, vendor, base-rate"
UNITS = "currency, percent, multiple, count, per-share"
TOGETHER = "^a finding's value and unit come together$"


@pytest.mark.parametrize(
    ("source", "extra", "message"),
    [
        ({"kind": "blog", "ref": "x"}, {}, f"^a source kind is one of {KINDS}, not 'blog'$"),
        (
            {"kind": "filing", "ref": "x"},
            {"value": 1.0, "unit": "usd"},
            f"^a unit is one of {UNITS}",
        ),
        ({"kind": "filing"}, {}, "^a finding's source needs a ref$"),
        ({"kind": "filing", "ref": " "}, {}, "^a finding's source needs a ref$"),
        ({"kind": "filing", "ref": "x"}, {"value": 1.0}, TOGETHER),
        ({"kind": "filing", "ref": "x"}, {"unit": "percent"}, TOGETHER),
        (
            {"kind": "filing", "ref": "x"},
            {"value": float("nan"), "unit": "percent"},
            "^a finding's value is a finite number$",
        ),
    ],
)
def test_a_finding_refuses_an_unknown_source_kind_or_unit(
    conn: sqlite3.Connection, source: dict[str, Any], extra: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        add_finding(conn, "AAPL", date(2026, 7, 31), "a fact", source, AGENT, NOW, **extra)
    assert findings_for(conn, "AAPL") == []


def test_a_finding_names_the_currency_of_its_money(conn: sqlite3.Connection) -> None:
    """Spec 2026-11-15 9.1: a money figure may name the currency the company states it in, stored
    as given, also when it is the reporting currency; a finding that names none is in the
    reporting currency, as every finding before."""
    capex = add_finding(
        conn,
        "TSM",
        date(2026, 10, 16),
        "capex guided at US$42 billion",
        FILING,
        AGENT,
        NOW,
        value=42e9,
        unit="currency",
        period="2026",
        currency="USD",
    )
    dividend = add_finding(
        conn,
        "TSM",
        date(2026, 10, 16),
        "a dividend",
        FILING,
        AGENT,
        NOW,
        value=6.0,
        unit="per-share",
        currency="TWD",
    )
    bare = add_finding(
        conn, "TSM", date(2026, 10, 16), "revenue", FILING, AGENT, NOW, value=3e12, unit="currency"
    )
    stored = {f.id: f.currency for f in findings_for(conn, "TSM")}
    assert stored == {capex: "USD", dividend: "TWD", bare: None}
    found = finding_row(conn, capex)
    assert found is not None
    assert (found.value, found.unit, found.currency) == (42e9, "currency", "USD")


MONEY = "a currency goes with a money figure"


def _form(code: str) -> str:
    return f"a currency is three capital letters, not {code!r}"


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ({"value": 0.112, "unit": "percent", "currency": "USD"}, MONEY),
        ({"value": 3.0, "unit": "multiple", "currency": "USD"}, MONEY),
        ({"currency": "USD"}, MONEY),  # no value
        ({"value": 1.0, "unit": "currency", "currency": "usd"}, _form("usd")),
        ({"value": 1.0, "unit": "currency", "currency": "US"}, _form("US")),
        ({"value": 1.0, "unit": "per-share", "currency": "DOLLAR"}, _form("DOLLAR")),
    ],
)
def test_a_finding_refuses_a_currency_off_a_money_figure_or_out_of_form(
    conn: sqlite3.Connection, extra: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        add_finding(conn, "TSM", date(2026, 10, 16), "a fact", FILING, AGENT, NOW, **extra)
    assert findings_for(conn, "TSM") == []


def test_kill_criteria(conn: sqlite3.Connection) -> None:
    first = add_kill_criterion(conn, "AAPL", "services growth below 5% for two years", AGENT, NOW)
    second = add_kill_criterion(conn, "AAPL", "gross margin below 40%", AGENT, LATER, report_id=3)
    assert kill_criteria_for(conn, "AAPL") == [
        KillCriterionRow(
            id=second,
            symbol="AAPL",
            text="gross margin below 40%",
            state="open",
            report_id=3,
            **BY_AGENT,
            at=LATER,
            state_reason=None,
            state_at=None,
        ),
        KillCriterionRow(
            id=first,
            symbol="AAPL",
            text="services growth below 5% for two years",
            state="open",
            report_id=None,
            **BY_AGENT,
            at=NOW,
            state_reason=None,
            state_at=None,
        ),
    ]
    with pytest.raises(ValueError, match="^a kill criterion needs text$"):
        add_kill_criterion(conn, "AAPL", "", AGENT, NOW)
    # a criterion recorded with no threshold is words alone, as every criterion before
    assert {(k.threshold, k.unit, k.currency) for k in kill_criteria_for(conn, "AAPL")} == {
        (None, None, None)
    }


def test_a_kill_criterion_holds_one_threshold_the_author_chose(conn: sqlite3.Connection) -> None:
    """Spec 2026-11-15 8.1: a criterion may hold one threshold, a number with its unit, one of a
    finding's, and for a money figure the currency it is in, stored as given; its text stays its
    statement."""
    growth = add_kill_criterion(
        conn,
        "TSM",
        "revenue growth below 5% for two years",
        AGENT,
        NOW,
        threshold=0.05,
        unit="percent",
    )
    capex = add_kill_criterion(
        conn,
        "TSM",
        "capital spending above US$50 billion",
        AGENT,
        LATER,
        threshold=50e9,
        unit="currency",
        currency="USD",
    )
    eps = add_kill_criterion(
        conn, "TSM", "EPS below TWD 40", AGENT, LATER, threshold=40.0, unit="per-share"
    )
    words = add_kill_criterion(conn, "TSM", "the chief executive leaves", AGENT, LATER)
    assert kill_criteria_for(conn, "TSM")[-1] == KillCriterionRow(
        id=growth,
        symbol="TSM",
        text="revenue growth below 5% for two years",
        state="open",
        report_id=None,
        **BY_AGENT,
        at=NOW,
        state_reason=None,
        state_at=None,
        threshold=0.05,
        unit="percent",
        currency=None,
    )
    stored = {k.id: (k.threshold, k.unit, k.currency) for k in kill_criteria_for(conn, "TSM")}
    assert stored == {
        growth: (0.05, "percent", None),
        capex: (50e9, "currency", "USD"),
        eps: (40.0, "per-share", None),
        words: (None, None, None),
    }
    found = kill_criterion_row(conn, capex)
    assert found is not None and (found.threshold, found.unit, found.currency) == (
        50e9,
        "currency",
        "USD",
    )


THRESHOLD_TOGETHER = "a kill criterion's threshold and unit come together"
ALL_UNITS = "currency, percent, multiple, count, per-share, score, years"


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ({"threshold": 0.05}, THRESHOLD_TOGETHER),
        ({"unit": "percent"}, THRESHOLD_TOGETHER),
        ({"threshold": 0.05, "unit": "usd"}, f"a unit is one of {ALL_UNITS}, not 'usd'"),
        (
            {"threshold": float("nan"), "unit": "percent"},
            "a kill criterion's threshold is a finite number",
        ),
        (
            {"threshold": float("inf"), "unit": "currency"},
            "a kill criterion's threshold is a finite number",
        ),
        ({"threshold": 0.05, "unit": "percent", "currency": "USD"}, MONEY),
        ({"currency": "USD"}, MONEY),  # no threshold
        ({"threshold": 1.0, "unit": "currency", "currency": "usd"}, _form("usd")),
    ],
)
def test_a_kill_criterion_refuses_a_threshold_out_of_form(
    conn: sqlite3.Connection, extra: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        add_kill_criterion(conn, "TSM", "a criterion", AGENT, NOW, **extra)
    assert kill_criteria_for(conn, "TSM") == []


def test_a_kill_criterion_moves_state_with_a_reason(conn: sqlite3.Connection) -> None:
    criterion = add_kill_criterion(conn, "AAPL", "gross margin below 40%", AGENT, NOW)
    with pytest.raises(ValueError, match="^a state change needs a reason$"):
        set_kill_criterion(conn, criterion, "triggered", " ", LATER)
    with pytest.raises(ValueError, match="^a kill criterion's state is open, triggered or retired"):
        set_kill_criterion(conn, criterion, "broken", "x", LATER)  # type: ignore[arg-type]
    with pytest.raises(AlreadyInState, match="^kill criterion 1 is already open$"):
        set_kill_criterion(conn, criterion, "open", "still holds", LATER)
    assert issubclass(AlreadyInState, ValueError)  # B-103 clause 1: the route's 409
    with pytest.raises(KeyError):
        set_kill_criterion(conn, 99, "retired", "x", LATER)
    moved = set_kill_criterion(conn, criterion, "triggered", "Q3 gross margin 39.8%", LATER)
    assert (moved.state, moved.state_reason, moved.state_at) == (
        "triggered",
        "Q3 gross margin 39.8%",
        LATER,
    )
    assert kill_criteria_for(conn, "AAPL") == [moved]
    retired = set_kill_criterion(conn, criterion, "retired", "the thesis changed", LATER)
    assert (retired.state, retired.at) == ("retired", NOW)


def test_news_items(conn: sqlite3.Connection) -> None:
    criterion = add_kill_criterion(conn, "AAPL", "gross margin below 40%", AGENT, NOW)
    first = add_news_item(
        conn,
        "AAPL",
        date(2026, 10, 30),
        "Q4 results",
        "https://example.com/q4",
        "gross margin 41.2%",
        AGENT,
        NOW,
        kill_criterion_id=criterion,
    )
    second = add_news_item(
        conn, "aapl", date(2026, 11, 2), "a new chip", "response:12", "a launch", OWNER, LATER
    )
    assert news_items_for(conn, "AAPL") == [
        NewsItemRow(
            id=second,
            symbol="AAPL",
            date=date(2026, 11, 2),
            headline="a new chip",
            source="response:12",
            text="a launch",
            kill_criterion_id=None,
            report_id=None,
            **BY_OWNER,
            at=LATER,
        ),
        NewsItemRow(
            id=first,
            symbol="AAPL",
            date=date(2026, 10, 30),
            headline="Q4 results",
            source="https://example.com/q4",
            text="gross margin 41.2%",
            kill_criterion_id=criterion,
            report_id=None,
            **BY_AGENT,
            at=NOW,
        ),
    ]
    other = add_kill_criterion(conn, "MSFT", "cloud growth below 10%", AGENT, NOW)
    for missing in (99, other):  # none, or another company's
        with pytest.raises(KeyError):
            add_news_item(
                conn,
                "AAPL",
                date(2026, 11, 2),
                "h",
                "s",
                "t",
                AGENT,
                NOW,
                kill_criterion_id=missing,
            )
    for blank in ("headline", "source", "text"):
        fields = {"headline": "h", "source": "s", "text": "t"} | {blank: " "}
        with pytest.raises(ValueError, match=f"^a news item needs its {blank}$"):
            add_news_item(conn, "AAPL", date(2026, 11, 2), writer=AGENT, at=NOW, **fields)
    assert len(news_items_for(conn, "AAPL")) == 2
