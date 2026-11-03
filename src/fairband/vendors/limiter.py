"""One vendor's pace, shared by every thread that calls through its client.

``RateLimiter.acquire`` takes the next slot under a lock and sleeps outside it until the slot
comes. Slots are one interval (60 / ``calls_per_minute`` seconds) apart, so the pace is even: in
any 60 seconds at most ``calls_per_minute`` calls start, plus the one whose slot was the window's
first instant. A caller who finds the next slot already past takes the present one: slots never
accumulate in the past. ``hold`` moves the next slot to ``seconds`` from now unless it is later
already, so after a vendor's 429 every thread's next call waits. A pace of 0 calls a minute is
none: ``acquire`` returns at once. ``totals`` counts, since the limiter was made, the calls
admitted, the seconds they waited for their slots and the holds taken; the refresh logs a fetch
stage's share of them.
"""

import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import NamedTuple


class PaceTotals(NamedTuple):
    """A limiter's counts: the calls admitted, the seconds they waited, the holds taken."""

    calls: int
    waited_s: float
    holds: int

    def since(self, earlier: "PaceTotals") -> "PaceTotals":
        """The counts added after ``earlier``, the same limiter's."""
        return PaceTotals(
            self.calls - earlier.calls, self.waited_s - earlier.waited_s, self.holds - earlier.holds
        )


class RateLimiter:
    """Admits calls at most ``calls_per_minute`` a minute, evenly spaced, in the order they
    arrive under the lock; admits every call at once when ``calls_per_minute`` is 0 or less."""

    def __init__(
        self,
        calls_per_minute: float,
        clock: Callable[[], datetime],
        sleep: Callable[[float], None],
    ) -> None:
        self.calls_per_minute = calls_per_minute
        paced = calls_per_minute > 0
        self.interval = timedelta(seconds=60 / calls_per_minute) if paced else timedelta(0)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next: datetime | None = None  # the next free slot; None until a call or a hold
        self._totals = PaceTotals(0, 0.0, 0)

    def acquire(self) -> float:
        """Waits for the next slot and returns the seconds waited."""
        waited = 0.0
        with self._lock:
            if self.calls_per_minute > 0:
                now = self._clock()
                slot = now if self._next is None else max(now, self._next)
                self._next = slot + self.interval
                waited = (slot - now).total_seconds()
            t = self._totals
            self._totals = t._replace(calls=t.calls + 1, waited_s=t.waited_s + waited)
        if waited > 0:
            self._sleep(waited)
        return waited

    def hold(self, seconds: float) -> None:
        """Moves the next slot to ``seconds`` from now, unless it is later already."""
        with self._lock:
            until = self._clock() + timedelta(seconds=seconds)
            self._next = until if self._next is None else max(self._next, until)
            self._totals = self._totals._replace(holds=self._totals.holds + 1)

    def totals(self) -> PaceTotals:
        """The calls admitted, the seconds they waited and the holds taken, so far."""
        with self._lock:
            return self._totals
