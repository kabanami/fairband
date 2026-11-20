"""The trailing P/E series Fairband builds from FMP's data (spec 2026-11-19 6.3, the text for
``method.md`` 16.7): a day's P/E is its close ÷ the trailing diluted EPS of the periods with the
latest ends at or before it, four quarters or two half-years; a loss day is a row with no point,
and a day without a trailing EPS, or without a rate for a company in another currency, is no row.
On synthetic closes and periods."""

from datetime import date

from fairband.reports.multiples import (
    STATS,
    PeriodEps,
    built_rows,
    built_series,
    period_eps,
)

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
