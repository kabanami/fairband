"""The server's refresh worker: one refresh at a time, on a daemon thread (spec 6.2, 6.10).

``start`` builds a ``Refresh`` with ``make_refresh`` (a cancel event of the run's own and the
worker's progress sink) and runs it on a daemon thread named ``fairband-refresh``. It returns the
refresh id once the run's record exists: ``Refresh.run`` hands it to ``on_started`` right after
``create_refresh``, and ``start`` waits for that, or for what the run raised before it, which it
raises again: ``RefreshRunning`` while another process runs a refresh, ``ValueError`` for a
request the run refuses. What ``make_refresh`` raises (the server's: stored settings the policy
no longer accepts) ``start`` raises as it comes. What the run raises after it started is kept,
scrubbed of the keys, as ``last_error`` and logged; the record carries the same message.

One refresh at a time: while the previous run's thread is alive, ``start`` raises
``RefreshRunning`` with its id at once. Once that thread has ended, ``start`` waits up to
``wait_s`` for the fetches the run gave up (``Refresh.fetches_in_flight``, after an exception in
its fetch stage) to end, so no given-up fetch writes while the next run works; else it raises
``RefreshRunning`` with the previous run's id. Then it closes the previous run's clients
(``Refresh.close``): each run holds clients of its own, built for it by ``make_refresh``, until
the next start. A run refused before its record closes its own at once.

``status`` is the latest ``Progress`` while the run's thread is alive, else ``None``; the record
says how the last run ended. The run writes its progress to the record as it goes
(``refreshes.stage``, ``refresh_items``). The thread is a daemon so that stopping the server never
waits for a run; the next start of the server marks the record ``interrupted``.
"""

import logging
import queue
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fairband.refresh.run import Kind, Progress, Refresh
from fairband.store.refreshes import RefreshRunning

logger = logging.getLogger("fairband.refresh")

type MakeRefresh = Callable[[threading.Event, Callable[[Progress], None]], Refresh]

THREAD_NAME = "fairband-refresh"
STARTING = "starting"  # the stage ``status`` reports before the run reports its first
_POLL_S = 0.05


@dataclass(frozen=True)
class _Run:
    refresh_id: int
    refresh: Refresh
    thread: threading.Thread
    cancel: threading.Event


class RefreshWorker:
    """Runs one refresh at a time on its own thread (see the module docstring)."""

    def __init__(self, make_refresh: MakeRefresh, wait_s: float = 5.0) -> None:
        self._make_refresh = make_refresh
        self._wait_s = wait_s
        self._lock = threading.Lock()  # one start at a time
        self._run: _Run | None = None
        self._progress: Progress | None = None
        self.last_error: str | None = None

    def start(self, kind: Kind, symbols: Sequence[str] | None = None) -> int:
        """Start a refresh of ``kind`` and return its id once its record exists."""
        with self._lock:
            if self._run is not None:
                self._wait_for(self._run)
                self._run.refresh.close()
            cancel = threading.Event()
            refresh = self._make_refresh(cancel, self._record)
            first: queue.Queue[int | BaseException] = queue.Queue()
            thread = threading.Thread(
                target=self._target,
                args=(refresh, kind, symbols, first),
                name=THREAD_NAME,
                daemon=True,
            )
            thread.start()
            outcome = first.get()
            if isinstance(outcome, BaseException):
                thread.join()
                refresh.close()
                raise outcome
            self._run = _Run(outcome, refresh, thread, cancel)
            return outcome

    def cancel(self) -> None:
        """Ask the run to stop after the companies in flight; nothing when none runs."""
        run = self._run
        if run is not None:
            run.cancel.set()

    def status(self) -> Progress | None:
        """The run's latest progress while its thread is alive, else ``None``."""
        run = self._run
        if run is None or not run.thread.is_alive():
            return None
        return self._progress

    def _target(
        self,
        refresh: Refresh,
        kind: Kind,
        symbols: Sequence[str] | None,
        first: queue.Queue[int | BaseException],
    ) -> None:
        """The run thread: hands ``first`` the refresh id once the record exists, or what the run
        raised before; keeps what it raises after."""
        started = False

        def on_started(refresh_id: int) -> None:
            nonlocal started
            started = True
            self.last_error = None
            self._progress = Progress(refresh_id, STARTING, 0, 0, 0, None)
            first.put(refresh_id)

        try:
            refresh.run(kind, symbols, on_started)
        except BaseException as exc:  # noqa: BLE001 - raised by start, or kept for the API
            if not started:
                first.put(exc)
                return
            self.last_error = refresh.describe(exc)
            logger.error("refresh failed: %s", self.last_error)

    def _record(self, progress: Progress) -> None:
        self._progress = progress

    def _wait_for(self, run: _Run) -> None:
        """Raise ``RefreshRunning`` at once while ``run``'s thread is alive; once it has ended,
        wait up to ``wait_s`` for the fetches it gave up to end, else raise it."""
        if run.thread.is_alive():
            raise RefreshRunning(run.refresh_id)
        deadline = time.monotonic() + self._wait_s
        while run.refresh.fetches_in_flight():
            if time.monotonic() >= deadline:
                raise RefreshRunning(run.refresh_id)
            time.sleep(_POLL_S)
