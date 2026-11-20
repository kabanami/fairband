"""The trailing P/E history's three FMP answers (spec 2026-11-19 6.3), synthetic, as FMP sends them
and as the pass-through stores them (``refresh.passthrough.series_answers``), for the tests that
need the series on a vendor double or in the store: the daily closes, the quarterly income
statements with their diluted EPS, and a pair's closes. ``unit_quarters`` gives every day from
2016 on a trailing EPS of 1.00, so a day's P/E is its close; ``report_in`` gives a company a
reporting currency."""

import json
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from fairband.engine.route import refusal_result
from fairband.policy import load_policy
from fairband.refresh.passthrough import FMP, series_answers
from fairband.store.snapshots import insert_snapshot
from fairband.store.vendor import record_response

FIRST_QUARTER = date(2015, 12, 31)  # 44 quarters from it end on 30 September 2026
_QUARTER_ENDS = ((3, 31), (6, 30), (9, 30), (12, 31))


def quarter_ends(first: date, count: int) -> list[date]:
    """``count`` consecutive calendar quarter ends from ``first``, itself one, oldest first."""
    ends, year, index = [], first.year, _QUARTER_ENDS.index((first.month, first.day))
    while len(ends) < count:
        month, day = _QUARTER_ENDS[index]
        ends.append(date(year, month, day))
        index = (index + 1) % 4
        if index == 0:
            year += 1
    return ends


def closes_payload(symbol: str, closes: Mapping[str, Any]) -> list[dict[str, Any]]:
    """FMP's ``historical-price-eod/full`` rows, newest first, each day with its close."""
    days = sorted(closes, reverse=True)
    return [{"symbol": symbol, "date": day, "close": closes[day]} for day in days]


def quarters_payload(
    symbol: str, eps: Iterable[tuple[date, Any]], currency: str | None = "USD"
) -> list[dict[str, Any]]:
    """FMP's quarterly ``income-statement`` rows, newest first, each period end with its
    ``epsDiluted`` and ``reportedCurrency`` (none where ``currency`` is ``None``)."""
    rows = []
    for end, value in sorted(eps, reverse=True):
        row = {"symbol": symbol, "date": end.isoformat(), "epsDiluted": value}
        if currency is not None:
            row["reportedCurrency"] = currency
        rows.append(row)
    return rows


def unit_quarters(
    symbol: str, losses: Iterable[date] = (), currency: str | None = "USD", eps: float = 0.25
) -> list[dict[str, Any]]:
    """44 quarters, 31 December 2015 to 30 September 2026, each with a diluted EPS of ``eps``, a
    year's four 1.00 at 0.25; a quarter end in ``losses`` has −4 × ``eps``, so each year of four
    quarters that holds it sums below zero, and the days from its end to the same day a year later
    are losses."""
    lost = set(losses)
    ends = quarter_ends(FIRST_QUARTER, 44)
    rows = [(end, -4 * eps if end in lost else eps) for end in ends]
    return quarters_payload(symbol, rows, currency)


def rates_payload(pair: str, rates: Mapping[str, Any]) -> list[dict[str, Any]]:
    """FMP's ``historical-price-eod/light`` rows of a pair, newest first, each day with its
    ``price``, units of the currency per USD."""
    days = sorted(rates, reverse=True)
    return [{"symbol": pair, "date": day, "price": rates[day]} for day in days]


def store_pe_history(
    conn: sqlite3.Connection,
    symbol: str,
    payloads: Mapping[str, Any],
    at: datetime,
    currency: str = "USD",
    error: str | None = None,
) -> dict[str, int]:
    """Store each part's payload (``closes``, ``quarters``, ``rates``) as the pass-through stores
    it for ``symbol`` reporting in ``currency``, observed ``at``, with ``error`` if given; the
    response ids by part."""
    answers = series_answers(symbol, currency)
    ids = {}
    for part, payload in payloads.items():
        answer = answers[part]
        text = json.dumps(payload)
        ids[part] = record_response(
            conn, FMP, answer.endpoint, answer.params, answer.symbol, 200, text, error, at
        )
    return ids


def report_in(conn: sqlite3.Connection, symbol: str, currency: str) -> None:
    """Give ``symbol`` the reporting currency ``currency`` (``store.currency.reporting_currency``):
    a snapshot refused with the currency its one intermediate, as assembly hands the engine a row
    refused for its currency, under the newest refresh."""
    [refresh_id] = conn.execute("SELECT max(id) FROM refreshes").fetchone()
    assert refresh_id is not None, "the database holds no refresh"
    refused = refusal_result(
        symbol, "refused", load_policy(), date(2026, 10, 31), intermediates={"currency": currency}
    )
    insert_snapshot(conn, refused, refresh_id, clock=lambda: datetime(2026, 11, 1, tzinfo=UTC))
