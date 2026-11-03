"""The rate limiter on a fake clock; real threads only where the lock is the point."""

import threading
from datetime import UTC, datetime, timedelta

from fairband.vendors.limiter import PaceTotals, RateLimiter

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)


class FakeTime:
    """The clock and the sleep: the clock moves only when a test sets it or a sleep passes, so
    the limiter's slots pass only as its callers sleep through them. Every sleep is recorded."""

    def __init__(self) -> None:
        self.now = T0
        self.sleeps: list[float] = []

    def clock(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += timedelta(seconds=seconds)

    def at(self, seconds: float) -> None:
        self.now = T0 + timedelta(seconds=seconds)


def test_sixty_a_minute_spaces_calls_one_second_apart() -> None:
    # Three callers arrive at t = 0, one after another under the lock: each finds the clock at 0.
    time = FakeTime()
    limiter = RateLimiter(60, time.clock, time.sleep)
    waits = []
    for _ in range(3):
        time.at(0)
        waits.append(limiter.acquire())
    assert waits == [0, 1, 2] and time.sleeps == [1, 2]
    assert time.now == T0 + timedelta(seconds=2)  # the last one wakes at its slot


def test_zero_a_minute_never_waits() -> None:
    time = FakeTime()
    limiter = RateLimiter(0, time.clock, time.sleep)
    assert [limiter.acquire() for _ in range(10)] == [0.0] * 10
    assert time.sleeps == []


def test_a_hold_moves_every_next_slot() -> None:
    time = FakeTime()
    limiter = RateLimiter(60, time.clock, time.sleep)
    time.at(5)
    limiter.hold(60)  # a 429 at t = 5 with no Retry-After holds the next slot to t = 65
    time.at(10)
    assert limiter.acquire() == 55
    assert time.now == T0 + timedelta(seconds=65)
    # The next slot is t = 66; a hold that ends before it changes nothing.
    limiter.hold(0.5)
    assert limiter.acquire() == 1
    assert time.sleeps == [55, 1]


def test_sixteen_threads_take_distinct_slots() -> None:
    # The clock stands at t = 0 and the sleep only records: each wait is the caller's slot.
    sleeps: list[float] = []
    limiter = RateLimiter(600, lambda: T0, sleeps.append)
    start = threading.Barrier(16)
    waits: list[float] = []
    lock = threading.Lock()

    def call() -> None:
        start.wait()
        waited = limiter.acquire()
        with lock:
            waits.append(waited)

    threads = [threading.Thread(target=call) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(waits) == [k / 10 for k in range(16)]
    assert sorted(sleeps) == [k / 10 for k in range(1, 16)]  # the first slot is now: no sleep


def test_a_late_arrival_starts_from_now_not_from_the_last_slot() -> None:
    time = FakeTime()
    limiter = RateLimiter(60, time.clock, time.sleep)
    assert limiter.acquire() == 0
    time.at(100)
    assert limiter.acquire() == 0  # slots never accumulate in the past
    time.at(100)
    assert limiter.acquire() == 1
    assert time.sleeps == [1]


def test_the_totals_count_calls_waits_and_holds() -> None:
    # Three callers at t = 0 wait 0, 1 and 2 s; a hold at t = 2 to t = 62 and one more call,
    # which waits 60 s. The totals since a mark are the counts after it.
    time = FakeTime()
    limiter = RateLimiter(60, time.clock, time.sleep)
    assert limiter.totals() == PaceTotals(0, 0.0, 0)
    for _ in range(3):
        time.at(0)
        limiter.acquire()
    mark = limiter.totals()
    assert mark == PaceTotals(3, 3.0, 0)
    limiter.hold(60)
    assert limiter.acquire() == 60
    assert limiter.totals() == PaceTotals(4, 63.0, 1)
    assert limiter.totals().since(mark) == PaceTotals(1, 60.0, 1)


def test_an_unpaced_limiter_counts_its_calls_and_holds() -> None:
    time = FakeTime()
    limiter = RateLimiter(0, time.clock, time.sleep)
    for _ in range(5):
        limiter.acquire()
    limiter.hold(60)
    assert limiter.totals() == PaceTotals(5, 0.0, 1)
    assert time.sleeps == []
