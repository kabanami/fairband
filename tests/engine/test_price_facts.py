from datetime import date, timedelta

import pytest

from fairband.engine.price_facts import PriceFacts, price_facts

TODAY = date(2026, 10, 31)


def test_price_facts_full_history() -> None:
    closes = [
        (date(2026, 10, 30), 100.0),  # the last close
        (date(2024, 6, 3), 200.0),  # the peak, outside the 52 weeks
        (date(2021, 10, 29), 50.0),  # five years back falls on a Sunday: the Friday before
        (date(2026, 11, 2), 500.0),  # after today: ignored
        (date(2025, 11, 3), 150.0),  # the 52-week high
        (date(2023, 10, 31), 80.0),  # three years back
        (date(2026, 3, 2), 90.0),  # the 52-week low
        (date(2025, 11, 1), 140.0),  # the first day of the 52 weeks
        (date(2025, 10, 31), 40.0),  # 365 days back: outside the 52 weeks; the 1-year reference
    ]
    facts = price_facts(closes, TODAY)
    assert facts.high_52w == 150.0
    assert facts.low_52w == 90.0
    assert facts.change_1y == pytest.approx(100.0 / 40.0 - 1)
    assert facts.change_3y == pytest.approx(0.25)
    assert facts.change_5y == pytest.approx(1.0)
    assert facts.drawdown_from_peak == pytest.approx(-0.5)


def test_price_facts_short_history() -> None:
    start = date(2025, 5, 1)  # 18 months of daily closes, rising by 1 a day
    closes = [(start + timedelta(days=i), 100.0 + i) for i in range((TODAY - start).days)]
    facts = price_facts(closes, TODAY)
    assert facts.change_3y is None
    assert facts.change_5y is None
    assert facts.high_52w == 100.0 + (date(2026, 10, 30) - start).days
    assert facts.low_52w == 100.0 + (date(2025, 11, 1) - start).days
    last, year_ago = (
        100.0 + (date(2026, 10, 30) - start).days,
        100.0 + (date(2025, 10, 31) - start).days,
    )
    assert facts.change_1y == pytest.approx(last / year_ago - 1)
    assert facts.drawdown_from_peak == 0.0


def test_change_needs_a_close_within_a_week() -> None:
    closes = [(date(2025, 10, 24), 80.0), (date(2026, 10, 30), 100.0)]
    assert price_facts(closes, TODAY).change_1y == pytest.approx(0.25)  # 7 days before
    closes = [(date(2025, 10, 23), 80.0), (date(2026, 10, 30), 100.0)]
    assert price_facts(closes, TODAY).change_1y is None  # 8 days before


def test_no_closes_in_the_52_weeks() -> None:
    facts = price_facts([(date(2024, 1, 2), 100.0)], TODAY)
    assert facts.high_52w is None and facts.low_52w is None
    assert facts.drawdown_from_peak == 0.0


def test_leap_day() -> None:
    closes = [(date(2027, 2, 26), 80.0), (date(2028, 2, 29), 100.0)]
    assert price_facts(closes, date(2028, 2, 29)).change_1y == pytest.approx(0.25)


def test_skips_non_positive_closes() -> None:
    closes = [(date(2025, 10, 31), 0.0), (date(2026, 10, 30), 100.0)]
    facts = price_facts(closes, TODAY)
    assert facts.change_1y is None
    assert facts.low_52w == 100.0


@pytest.mark.parametrize("closes", [[], [(date(2026, 11, 2), 100.0)]])
def test_no_closes(closes: list[tuple[date, float]]) -> None:
    assert price_facts(closes, TODAY) == PriceFacts(None, None, None, None, None, None)
