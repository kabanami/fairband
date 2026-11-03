"""The statement facts backfill over responses stored before the normalizer kept the six lines.

Each test stores a synthetic response of each statement kind through ``record_response`` with the
facts the normalizer kept before (every field but the six), as a refresh before the change did.
"""

import json
import logging
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from synthetic import QUARTERS, SIX_LINES, M, statement

from fairband.refresh.backfill import backfill_statement_facts
from fairband.store.facts import facts_for, insert_facts
from fairband.store.vendor import record_response
from fairband.vendors.normalize_fmp import statement_facts

OBSERVED = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
# The six lines by statement.
NEW = {
    "income-annual": {"grossProfit", "interestExpense"},
    "income-quarter": {"grossProfit", "interestExpense"},
    "balance-annual": {"totalAssets", "totalLiabilities", "retainedEarnings"},
    "cashflow-annual": {"depreciationAndAmortization"},
    "cashflow-quarter": {"depreciationAndAmortization"},
}
SIX = set(SIX_LINES)


def income(day: date, period: str) -> dict[str, Any]:
    """Interest expense signed negative, as FMP signs it for some companies."""
    return statement(
        day, day.year, period, revenue=300 * M, grossProfit=120 * M, interestExpense=-4 * M
    )


def balance(day: date) -> dict[str, Any]:
    return statement(
        day,
        day.year,
        "FY",
        totalCurrentAssets=600 * M,
        totalAssets=1500 * M,
        totalLiabilities=800 * M,
        retainedEarnings=None,  # not presented
    )


def cashflow(day: date, period: str) -> dict[str, Any]:
    return statement(day, day.year, period, depreciationAndAmortization=15 * M)


YEARS = (date(2024, 12, 31), date(2025, 12, 31))
Q2, Q3 = QUARTERS[-2:]  # 2026
PAYLOADS = {
    "income-annual": [income(d, "FY") for d in YEARS],
    "income-quarter": [income(Q2, "Q2"), income(Q3, "Q3")],
    "balance-annual": [balance(d) for d in YEARS],
    "cashflow-annual": [cashflow(d, "FY") for d in YEARS],
    "cashflow-quarter": [cashflow(Q2, "Q2"), cashflow(Q3, "Q3")],
}


def store_before_the_change(
    conn: sqlite3.Connection, endpoint: str, payload: Any, symbol: str = "ACME"
) -> int:
    """A usable response and the facts the normalizer kept before the six lines; its id."""
    text = json.dumps(payload)
    params = {"symbol": symbol, "period": "annual", "limit": "11"}
    response_id = record_response(conn, "fmp", endpoint, params, symbol, 200, text, None, OBSERVED)
    facts = statement_facts(payload, symbol, endpoint, response_id, OBSERVED, OBSERVED)
    insert_facts(conn, [f for f in facts if f.field not in SIX])
    return response_id


def fields_of(conn: sqlite3.Connection, response_id: int) -> list[tuple[str, str]]:
    """Each fact of the response as (period end, field), in insertion order."""
    rows = conn.execute(
        "SELECT period_end, field FROM facts WHERE response_id = ? ORDER BY id", (response_id,)
    )
    return [(row[0], row[1]) for row in rows]


def count_facts(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM facts").fetchone()[0])


def test_backfill_writes_the_six_lines_once(conn: sqlite3.Connection) -> None:
    ids = {
        endpoint: store_before_the_change(conn, endpoint, payload)
        for endpoint, payload in PAYLOADS.items()
    }
    before = {endpoint: fields_of(conn, rid) for endpoint, rid in ids.items()}
    assert not SIX & {field for rows in before.values() for _, field in rows}

    # Two periods each: 2 × 2 income lines twice, 2 × 3 balance lines, 2 × 1 cash-flow line twice.
    assert backfill_statement_facts(conn, NOW) == 4 + 4 + 6 + 2 + 2
    for endpoint, rid in ids.items():
        after = fields_of(conn, rid)
        assert after[: len(before[endpoint])] == before[endpoint]  # nothing else touched
        added = after[len(before[endpoint]) :]
        assert {field for _, field in added} == NEW[endpoint]
        assert len(added) == 2 * len(NEW[endpoint])

    interest = [
        f for f in facts_for(conn, "ACME", "income-quarter") if f.field == "interestExpense"
    ]
    # Each row as a fetch stores it: the vendor's sign, the period's labels and currency.
    assert [(f.period_end, f.value, f.fiscal_period) for f in interest] == [
        (Q2, Decimal(-4 * M), "Q2"),
        (Q3, Decimal(-4 * M), "Q3"),
    ]
    for fact in interest:
        assert fact.response_id == ids["income-quarter"]  # cites the response it was read from
        assert (fact.observed_at, fact.entered_at) == (OBSERVED, NOW)
        assert (fact.fiscal_year, fact.currency, fact.unit) == (2026, "USD", "currency")
    retained = [
        f for f in facts_for(conn, "ACME", "balance-annual") if f.field == "retainedEarnings"
    ]
    assert {(f.value, f.missing_reason) for f in retained} == {(None, "null")}

    total = count_facts(conn)
    assert backfill_statement_facts(conn, NOW + timedelta(hours=1)) == 0
    assert count_facts(conn) == total


def test_backfill_reads_every_usable_response_of_every_symbol(conn: sqlite3.Connection) -> None:
    """An older response restating the same periods and another symbol's both gain the lines."""
    older = store_before_the_change(conn, "income-annual", PAYLOADS["income-annual"])
    newer = store_before_the_change(conn, "income-annual", PAYLOADS["income-annual"])
    other = store_before_the_change(conn, "income-annual", PAYLOADS["income-annual"], "BOLT")
    assert backfill_statement_facts(conn, NOW) == 3 * 4
    for rid in (older, newer, other):
        assert {"grossProfit", "interestExpense"} <= {field for _, field in fields_of(conn, rid)}


def test_backfill_skips_a_response_with_an_error_or_without_a_payload(
    conn: sqlite3.Connection,
) -> None:
    payload = json.dumps(PAYLOADS["income-annual"])
    params = {"symbol": "ACME", "period": "annual", "limit": "11"}
    unusable = "unusable payload: [...]"
    record_response(conn, "fmp", "income-annual", params, "ACME", 200, payload, unusable, OBSERVED)
    record_response(conn, "fmp", "income-annual", params, "ACME", 200, None, None, OBSERVED)
    record_response(conn, "fmp", "income-annual", params, "ACME", 500, payload, None, OBSERVED)
    record_response(conn, "fmp", "income-annual", params, "ACME", None, None, "timeout", OBSERVED)
    # Not a statement endpoint: its payload is never read as one.
    record_response(conn, "fmp", "profile", {"symbol": "ACME"}, "ACME", 200, "[]", None, OBSERVED)
    assert backfill_statement_facts(conn, NOW) == 0
    assert count_facts(conn) == 0


def test_backfill_writes_nothing_for_a_response_stored_after_the_change(
    conn: sqlite3.Connection,
) -> None:
    text = json.dumps(PAYLOADS["balance-annual"])
    params = {"symbol": "ACME", "period": "annual", "limit": "11"}
    rid = record_response(conn, "fmp", "balance-annual", params, "ACME", 200, text, None, OBSERVED)
    insert_facts(
        conn,
        statement_facts(PAYLOADS["balance-annual"], "ACME", "balance-annual", rid, OBSERVED, NOW),
    )
    total = count_facts(conn)
    assert backfill_statement_facts(conn, NOW) == 0
    assert count_facts(conn) == total


def test_backfill_logs_its_count(
    conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    store_before_the_change(conn, "cashflow-annual", PAYLOADS["cashflow-annual"])
    with caplog.at_level(logging.INFO, logger="fairband.refresh"):
        backfill_statement_facts(conn, NOW)
        backfill_statement_facts(conn, NOW)
    assert [r.getMessage() for r in caplog.records] == [
        "statement backfill: 2 facts written",
        "statement backfill: 0 facts written",
    ]
