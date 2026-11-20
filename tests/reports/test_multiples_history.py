"""The trailing P/E series Fairband builds from FMP's data (spec 2026-11-19 6.3, the text for
``method.md`` 16.7): a day's P/E is its close ÷ the trailing diluted EPS of the periods with the
latest ends at or before it, four quarters or two half-years; a loss day is a row with no point,
and a day without a trailing EPS, or without a rate for a company in another currency, is no row.
On synthetic closes and periods; then the series of the three answers as FMP sends them
(``trailing_series``), and as the pass-through stores them (``stored_trailing``)."""

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from support.pe_history import (
    closes_payload,
    quarters_payload,
    rates_payload,
    report_in,
    store_pe_history,
)

from fairband.reports.multiples import (
    STATS,
    PeriodEps,
    built_rows,
    built_series,
    period_eps,
    stored_series,
    stored_trailing,
    trailing_series,
)
from fairband.store.vendor import record_response

AT = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
Q = [date(2025, 3, 31), date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31), date(2026, 3, 31)]


def _periods(eps, currency="USD", ends=Q):
    return [PeriodEps(end, e, currency) for end, e in zip(ends, eps)]


def test_the_eps_steps_at_a_period_end() -> None:
    closes = [(date(2026, 3, 30), 100.0), (date(2026, 3, 31), 100.0)]
    rows = built_rows(closes, _periods([1.0, 1.0, 1.0, 1.0, 2.0]), "USD", None)
    assert rows == [(date(2026, 3, 30), 25.0), (date(2026, 3, 31), 20.0)]


def test_a_loss_day_is_a_row_with_no_point() -> None:
    series = built_series(
        [(date(2026, 1, 5), 50.0)], _periods([1.0, -1.0, -1.0, -1.0]), "USD", None
    )
    assert (series.points, series.since) == ((), date(2026, 1, 5))
    assert series.stats == dict.fromkeys(STATS)


def test_a_half_yearly_reporter_sums_two_periods() -> None:
    ends = [date(2024, 12, 31), date(2025, 6, 30), date(2025, 12, 31)]
    rows = built_rows([(date(2026, 1, 5), 60.0)], _periods([9.0, 1.0, 2.0], ends=ends), "USD", None)
    assert rows == [(date(2026, 1, 5), 20.0)]


def test_another_currency_reads_the_close_at_the_days_rate() -> None:
    closes = [(date(2026, 1, 2), 10.0), (date(2026, 1, 5), 10.0)]
    rates = [(date(2026, 1, 5), 30.0)]
    rows = built_rows(closes, _periods([3.0, 4.0, 4.0, 4.0], "TWD"), "TWD", rates)
    assert rows == [(date(2026, 1, 5), 20.0)]  # 10 × 30 ÷ 15; no rate on 2 January


def test_periods_that_are_not_consecutive_give_no_row() -> None:
    ends = [date(2024, 12, 31), date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31)]
    assert built_rows([(date(2026, 1, 5), 50.0)], _periods([1.0] * 4, ends=ends), "USD", None) == []


def test_a_period_in_another_currency_gives_no_row() -> None:
    periods = [*_periods([1.0] * 3), PeriodEps(Q[3], 1.0, "CAD")]
    assert built_rows([(date(2026, 1, 5), 50.0)], periods, "USD", None) == []


def test_a_period_without_its_eps_gives_no_row() -> None:
    assert (
        built_rows([(date(2026, 1, 5), 50.0)], _periods([1.0, None, 1.0, 1.0]), "USD", None) == []
    )


def test_period_eps_reads_text_and_missing_lines_as_none() -> None:
    payload = [
        {"date": "2025-12-31", "epsDiluted": "n/a", "reportedCurrency": "USD"},
        {"date": "2025-09-30", "reportedCurrency": "USD"},
    ]
    assert [p.eps for p in period_eps(payload)] == [None, None]
    assert period_eps({"error": "x"}) is None


def test_period_eps_reads_the_rows_oldest_first() -> None:
    payload = [
        {"date": "2025-12-31", "epsDiluted": 1.25, "reportedCurrency": "EUR"},
        {"date": "2025-09-30", "epsDiluted": "0.5", "reportedCurrency": "EUR"},
        {"epsDiluted": 9.0, "reportedCurrency": "EUR"},
    ]
    assert period_eps(payload) == [
        PeriodEps(date(2025, 9, 30), 0.5, "EUR"),
        PeriodEps(date(2025, 12, 31), 1.25, "EUR"),
    ]


def test_a_rate_holds_until_the_pairs_next_close() -> None:
    closes = [(date(2026, 1, 6), 10.0), (date(2026, 1, 8), 10.0)]
    rates = [(date(2026, 1, 7), 15.0), (date(2026, 1, 2), 30.0)]
    rows = built_rows(closes, _periods([3.0, 4.0, 4.0, 4.0], "TWD"), "TWD", rates)
    assert rows == [(date(2026, 1, 6), 20.0), (date(2026, 1, 8), 10.0)]


def test_no_close_and_no_period_give_an_empty_series() -> None:
    series = built_series([], [], "USD", None)
    assert (series.points, series.since) == ((), None)


def test_a_trailing_eps_of_exactly_zero_is_a_loss_day() -> None:
    rows = built_rows([(date(2026, 1, 5), 50.0)], _periods([0.5, -0.5, 0.25, -0.25]), "USD", None)
    assert rows == [(date(2026, 1, 5), None)]


def test_rows_that_give_no_cadence_fall_back_to_quarterly() -> None:
    """The two newest periods end 120 days apart, no cadence (``cadence_of``): the year is four
    quarters, so the day after the fourth sums them, and a year that holds the gap has no sum."""
    ends = [*Q[:4], date(2026, 4, 30)]
    closes = [(date(2026, 1, 5), 40.0), (date(2026, 5, 4), 40.0)]
    rows = built_rows(closes, _periods([1.0] * 5, ends=ends), "USD", None)
    assert rows == [(date(2026, 1, 5), 10.0)]


def test_another_currency_without_rates_gives_no_row() -> None:
    periods = _periods([3.0, 4.0, 4.0, 4.0], "TWD")
    assert built_rows([(date(2026, 1, 5), 10.0)], periods, "TWD", None) == []


def test_a_period_with_no_stated_currency_is_in_the_reporting_currency() -> None:
    """The ruling on Task 4's review: a statement that names no currency is read in the reporting
    currency, as ``method.md`` 4.2 reads one."""
    periods = [*_periods([3.0, 4.0, 4.0], "TWD"), PeriodEps(Q[3], 4.0, None)]
    rows = built_rows([(date(2026, 1, 5), 10.0)], periods, "TWD", [(date(2026, 1, 5), 30.0)])
    assert rows == [(date(2026, 1, 5), 20.0)]
    unstated = _periods([1.0, 1.0, 1.0, 1.0], None)
    rows = built_rows([(date(2026, 1, 5), 50.0)], unstated, "USD", None)
    assert rows == [(date(2026, 1, 5), 12.5)]


def _parts(
    closes: dict[str, Any],
    currency: str | None = "USD",
    rates: dict[str, Any] | None = None,
    eps: float = 3.75,
) -> dict[str, Any]:
    """The three answers by part as FMP sends them: ``closes`` by ISO day; the four quarters of
    2025, each with a diluted EPS of ``eps`` in ``currency``; and the pair's closes by ISO day,
    where given."""
    parts = {
        "closes": closes_payload("TWCO", closes),
        "quarters": quarters_payload("TWCO", [(end, eps) for end in Q[:4]], currency),
    }
    if rates is not None:
        parts["rates"] = rates_payload("USDTWD", rates)
    return parts


def test_the_series_of_the_three_answers() -> None:
    """The close in USD at the pair's rate, ÷ the four quarters' diluted EPS in TWD: 10 × 30 ÷ 15
    and 11 × 30 ÷ 15; a day before the pair's first close has no rate and no row. In USD the pair
    is not read: 30 ÷ 15."""
    closes = {"2026-01-02": 9.0, "2026-01-05": 10.0, "2026-01-06": 11.0}
    parts = _parts(closes, "TWD", {"2026-01-05": 30.0})
    series = trailing_series(parts, "TWD")
    assert series is not None and series.since == date(2026, 1, 5)
    assert series.points == ((date(2026, 1, 5), 20.0), (date(2026, 1, 6), 22.0))
    usd = trailing_series(_parts({"2026-01-05": 30.0}, rates={"2026-01-05": 99.0}), "USD")
    assert usd is not None and usd.points == ((date(2026, 1, 5), 2.0),)


@pytest.mark.parametrize("unread", [None, {"Error Message": "Limit Reach"}, "[]"])
def test_a_series_whose_closes_or_quarters_cannot_be_read_is_none(unread: Any) -> None:
    """A part missing, or not a list (FMP's error object, a text): no series."""
    for part in ("closes", "quarters"):
        parts = _parts({"2026-01-05": 30.0})
        if unread is None:
            del parts[part]
        else:
            parts[part] = unread
        assert trailing_series(parts, "USD") is None, part


@pytest.mark.parametrize("unread", [None, {"Error Message": "Limit Reach"}])
def test_a_series_in_another_currency_whose_rates_cannot_be_read_is_none(unread: Any) -> None:
    parts = _parts({"2026-01-05": 10.0}, "TWD", {"2026-01-05": 30.0})
    if unread is None:
        del parts["rates"]
    else:
        parts["rates"] = unread
    assert trailing_series(parts, "TWD") is None


def test_empty_answers_give_a_series_with_no_point() -> None:
    """A company listed last month: FMP answers each deep call with an empty list. The series
    reads, with no point, no statistic and no first day (Review Focus 3)."""
    empty: dict[str, Any] = {"closes": [], "quarters": [], "rates": []}
    for currency in ("USD", "TWD"):
        series = trailing_series(empty, currency)
        assert series is not None, currency
        assert (series.points, series.since) == ((), None)
        assert series.stats == dict.fromkeys(STATS)


@pytest.mark.parametrize("bad", [0, 0.0, -10.0, "n/a", None, "1e400"])
def test_a_close_that_is_not_a_positive_number_gives_no_row(bad: Any) -> None:
    series = trailing_series(_parts({"2026-01-05": bad, "2026-01-06": 30.0}), "USD")
    assert series is not None and series.points == ((date(2026, 1, 6), 2.0),)
    assert series.since == date(2026, 1, 6)


@pytest.mark.parametrize("bad", [0, 0.0, -30.0, "n/a", None, "1e400"])
def test_a_rate_that_is_not_a_positive_number_is_not_read(bad: Any) -> None:
    """A bad rate is no rate: with none before it the day has no row; with one before it, the
    day reads that one."""
    closes = {"2026-01-05": 10.0}
    alone = trailing_series(_parts(closes, "TWD", {"2026-01-05": bad}), "TWD")
    assert alone is not None and alone.points == ()
    earlier = trailing_series(_parts(closes, "TWD", {"2026-01-02": 30.0, "2026-01-05": bad}), "TWD")
    assert earlier is not None and earlier.points == ((date(2026, 1, 5), 20.0),)


def _seed(conn: sqlite3.Connection, at: datetime = AT) -> int:
    """TWCO reporting in TWD, with its three answers stored, observed ``at``: a close of USD 10 on
    5 January 2026 at TWD 30 per USD, ÷ TWD 15 of trailing EPS. The closes' response id."""
    report_in(conn, "TWCO", "TWD")
    parts = _parts({"2026-01-05": 10.0}, "TWD", {"2026-01-05": 30.0})
    return store_pe_history(conn, "TWCO", parts, at, "TWD")["closes"]


def test_stored_trailing_reads_the_three_answers(conn: sqlite3.Connection) -> None:
    closes_id = _seed(conn)
    stored = stored_trailing(conn, "TWCO")
    assert stored is not None and stored[0] == closes_id
    assert stored[1] is not None and stored[1].points == ((date(2026, 1, 5), 20.0),)
    assert stored_series(conn, "TWCO", "pe") == stored[1]


def test_stored_trailing_reads_the_newest_usable_answer_of_each_whatever_its_age(
    conn: sqlite3.Connection,
) -> None:
    """The answers stored a year ago; since then newer closes, and a newer pair stored unusable:
    the newer closes, the year-old quarters and the year-old pair are read."""
    _seed(conn, AT - timedelta(days=365))
    closes = {"closes": closes_payload("TWCO", {"2026-01-05": 11.0})}
    newer = store_pe_history(conn, "TWCO", closes, AT, "TWD")["closes"]
    unusable = {"rates": rates_payload("USDTWD", {"2026-01-05": 60.0})}
    store_pe_history(conn, "TWCO", unusable, AT, "TWD", error="unusable payload: x")
    stored = stored_trailing(conn, "TWCO")
    assert stored is not None and stored[0] == newer
    assert stored[1] is not None and stored[1].points == ((date(2026, 1, 5), 22.0),)


def test_stored_trailing_needs_the_closes_and_the_quarters(conn: sqlite3.Connection) -> None:
    parts = _parts({"2026-01-05": 30.0})
    for part, symbol in (("closes", "CLCO"), ("quarters", "QUCO")):
        store_pe_history(conn, symbol, {part: parts[part]}, AT)
        assert stored_trailing(conn, symbol) is None, part
        assert stored_series(conn, symbol, "pe") is None, part


def test_stored_trailing_in_another_currency_without_the_pair_cannot_be_read(
    conn: sqlite3.Connection,
) -> None:
    report_in(conn, "TWCO", "TWD")
    parts = _parts({"2026-01-05": 10.0}, "TWD")
    closes_id = store_pe_history(conn, "TWCO", parts, AT, "TWD")["closes"]
    assert stored_trailing(conn, "TWCO") == (closes_id, None)


def test_stored_trailing_does_not_read_an_old_gurufocus_answer(conn: sqlite3.Connection) -> None:
    """Review Focus 5: a database that holds GuruFocus's ``pettm`` answer and no ``pe-closes``
    has no stored trailing series, so a ref on the old series is unresolved."""
    old = json.dumps([["2026-10-30", 24.0, 24.0, 24.0, 24.0]])
    record_response(conn, "gf", "pettm", {"symbol": "ACME"}, "ACME", 200, old, None, AT)
    assert stored_trailing(conn, "ACME") is None
    assert stored_series(conn, "ACME", "pe") is None
