"""The refresh runner: one refresh record, its stages and each company's progress (spec 6.2).

``Refresh.run("scoped", symbols)`` records the policy, starts a ``running`` refresh (while another
runs, ``create_refresh`` raises ``RefreshRunning``), lists each symbol ``pending`` and runs:

- ``fetch``: ``fetch_company`` for each symbol on ``policy.refresh.workers`` threads, each call on a
  connection of its own from ``conn_factory``. At most that many symbols are in flight, and the run
  starts the next only after it has recorded a finished one. A symbol becomes ``fetching``, then
  ``fetched``, or ``failed`` with the fetch's error and a refusal snapshot of that reason ("data
  fetch failed: <endpoints>") that carries the price the store holds.
- ``value``: on the run's own connection, one fetched symbol at a time: ``build_inputs``,
  ``value_company`` with the latest stored deciles, ``insert_snapshot``; the symbol is ``valued``.
  Without stored deciles the snapshot is the refusal "no universe deciles yet" (spec 6.6).
- ``done``: the run's totals.

A symbol's failure never stops the run: an exception from its fetch, assembly or valuation gives it
a refusal snapshot ("data fetch failed: <class>: <message>" or "valuation failed: <class>:
<message>", the keys scrubbed), marks it ``failed`` and is logged as a warning.

The run stops early on two events. A cancel is read before each symbol starts, in both stages; the
symbols in flight finish and the run ends ``cancelled``, with no further stage: a fetched symbol
keeps its stored responses, which the next run reuses within ``reuse_hours``, and a valued one its
snapshot. An HTTP 429 (``FetchOutcome.rate_limited``) ends the fetching the same way; the symbol it
hit goes back to ``pending``, the symbols fetched are still valued, and the run ends ``failed``
with "rate limited by <provider>: stopped after <n> companies". An exception outside a symbol's
work ends the run ``failed`` with its class and message, and is raised again.

``on_progress`` gets a ``Progress`` at each stage change and after each symbol; it runs on the
thread that called ``run``.
"""

import logging
import sqlite3
import threading
from collections import deque
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from fairband.config import MissingKey
from fairband.engine import METHOD_VERSION
from fairband.engine.route import refusal_result, value_company
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.refresh.fetch import FetchOutcome, fetch_company, provider_of
from fairband.refresh.inputs import build_inputs, latest_price
from fairband.store.db import transaction
from fairband.store.policy import record_policy
from fairband.store.refreshes import (
    Finished,
    create_refresh,
    finish_refresh,
    latest_deciles,
    set_stage,
    upsert_item,
)
from fairband.store.snapshots import insert_snapshot
from fairband.vendors.fmp import Fmp
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.scrub import scrub

logger = logging.getLogger("fairband.refresh")

type Kind = Literal["full", "price", "scoped"]

_PROVIDER_NAMES = {"fmp": "FMP", "gf": "GuruFocus"}


@dataclass(frozen=True)
class Progress:
    """Where a refresh is. ``done``, ``failed`` and ``remaining`` count the current stage's
    symbols and add up to them: finished, failed, and the rest, those in flight among them.
    ``current`` is a symbol in flight (the first started), else ``None``. The ``done`` stage
    carries the run's totals: symbols valued, symbols failed in either stage, none remaining."""

    refresh_id: int
    stage: str
    done: int
    failed: int
    remaining: int
    current: str | None


@dataclass(frozen=True)
class _Fetched:
    """What the fetch stage left: the symbols fetched, how many failed, and the provider whose
    HTTP 429 stopped it, if one did."""

    symbols: tuple[str, ...]
    failed: int
    limited_by: str | None


class Refresh:
    """One refresh run (see the module docstring). ``conn_factory`` opens a connection to the
    store: ``run`` opens one for itself and each fetch one of its own. ``secrets`` are the vendor
    keys, scrubbed from what the fetch stores and from every message the run writes."""

    def __init__(
        self,
        conn_factory: Callable[[], sqlite3.Connection],
        fmp: Fmp | None,
        gf: GuruFocus | None,
        policy: Policy,
        tax: TaxTable,
        clock: Callable[[], datetime],
        cancel: threading.Event,
        on_progress: Callable[[Progress], None] | None = None,
        secrets: Sequence[str] = (),
    ) -> None:
        self._conn_factory = conn_factory
        self._fmp = fmp
        self._gf = gf
        self._policy = policy
        self._tax = tax
        self._clock = clock
        self._cancel = cancel
        self._on_progress = on_progress
        self._secrets = tuple(secrets)

    def run(self, kind: Kind, symbols: Sequence[str] | None = None) -> int:
        """Run a refresh of ``kind`` and return its id. Raises ``MissingKey`` without an FMP
        client and ``ValueError`` for a scoped refresh without symbols, both before any work."""
        fmp = self._fmp
        if fmp is None:
            raise MissingKey("fmp")
        if kind != "scoped":
            raise NotImplementedError(f"the {kind} refresh is built in a later task")
        if not symbols:
            raise ValueError("a scoped refresh needs symbols")
        names = list(dict.fromkeys(symbols))
        with closing(self._conn_factory()) as conn:
            record_policy(conn, self._policy, self._clock())
            refresh_id = create_refresh(
                conn, kind, names, self._policy.version, METHOD_VERSION, self._clock()
            )
            try:
                status, message = self._scoped(conn, fmp, refresh_id, names)
            except BaseException as exc:
                finish_refresh(conn, refresh_id, "failed", self._clock(), self._describe(exc))
                raise
            finish_refresh(conn, refresh_id, status, self._clock(), message)
        return refresh_id

    def _scoped(
        self, conn: sqlite3.Connection, fmp: Fmp, refresh_id: int, symbols: list[str]
    ) -> tuple[Finished, str | None]:
        """The stages of a scoped refresh; the status and message to finish it with."""
        with transaction(conn):
            for symbol in symbols:
                upsert_item(conn, refresh_id, symbol, "pending", None, self._clock())
        fetched = self._fetch_stage(conn, fmp, refresh_id, symbols)
        if fetched.limited_by is not None:
            self._value_stage(conn, refresh_id, fetched.symbols)
            reached = len(fetched.symbols) + fetched.failed
            noun = "company" if reached == 1 else "companies"
            return "failed", f"rate limited by {fetched.limited_by}: stopped after {reached} {noun}"
        if self._cancel.is_set():
            return "cancelled", None
        valued = self._value_stage(conn, refresh_id, fetched.symbols)
        if valued is None:
            return "cancelled", None
        set_stage(conn, refresh_id, "done")
        self._report(refresh_id, "done", valued, fetched.failed + len(fetched.symbols) - valued)
        return "done", None

    def _fetch_stage(
        self, conn: sqlite3.Connection, fmp: Fmp, refresh_id: int, symbols: Sequence[str]
    ) -> _Fetched:
        """Fetch ``symbols`` until all are fetched, a cancel or a 429."""
        self._stage(conn, refresh_id, "fetch", len(symbols))
        workers = self._policy.refresh.workers
        waiting = deque(symbols)
        running: dict[Future[FetchOutcome], str] = {}
        fetched: list[str] = []
        failed = 0
        limited_by: str | None = None
        with ThreadPoolExecutor(workers, thread_name_prefix="fairband-fetch") as pool:
            while True:
                while waiting and len(running) < workers:
                    if limited_by is not None or self._cancel.is_set():
                        break
                    symbol = waiting.popleft()
                    now = self._clock()
                    upsert_item(conn, refresh_id, symbol, "fetching", None, now)
                    running[pool.submit(self._fetch, fmp, symbol, now)] = symbol
                if not running:
                    break
                finished, _ = wait(running, return_when=FIRST_COMPLETED)
                for future in [f for f in running if f in finished]:  # in the order started
                    symbol = running.pop(future)
                    try:
                        outcome = future.result()
                    except Exception as exc:  # noqa: BLE001 - a symbol's failure is its own
                        reason = f"data fetch failed: {self._describe(exc)}"
                        self._fail(conn, refresh_id, symbol, reason)
                        failed += 1
                    else:
                        if outcome.rate_limited:
                            provider = _PROVIDER_NAMES[provider_of(outcome.failed[-1])]
                            limited_by = limited_by or provider
                            message = f"rate limited by {provider}"
                            upsert_item(conn, refresh_id, symbol, "pending", message, self._clock())
                        elif outcome.error is not None:
                            self._fail(conn, refresh_id, symbol, outcome.error)
                            failed += 1
                        else:
                            upsert_item(conn, refresh_id, symbol, "fetched", None, self._clock())
                            fetched.append(symbol)
                    current = next(iter(running.values()), None)
                    left = len(symbols) - len(fetched) - failed
                    self._report(refresh_id, "fetch", len(fetched), failed, left, current)
        return _Fetched(tuple(fetched), failed, limited_by)

    def _fetch(self, fmp: Fmp, symbol: str, now: datetime) -> FetchOutcome:
        """One symbol's fetch, on a worker thread with a connection of its own."""
        with closing(self._conn_factory()) as conn:
            return fetch_company(conn, fmp, self._gf, symbol, self._policy, now, self._secrets)

    def _value_stage(
        self, conn: sqlite3.Connection, refresh_id: int, symbols: Sequence[str]
    ) -> int | None:
        """Value ``symbols`` one at a time; the number valued, or ``None`` when a cancel
        stopped the stage."""
        self._stage(conn, refresh_id, "value", len(symbols))
        deciles = latest_deciles(conn)
        today = self._clock().date()
        valued = failed = 0
        for symbol in symbols:
            if self._cancel.is_set():
                return None
            try:
                inputs = build_inputs(conn, symbol, self._policy, self._tax, today)
                result = value_company(inputs, deciles, self._policy, today)
                with transaction(conn):
                    insert_snapshot(conn, result, refresh_id, clock=self._clock)
                    upsert_item(conn, refresh_id, symbol, "valued", None, self._clock())
            except Exception as exc:  # noqa: BLE001 - a symbol's failure is its own
                self._fail(conn, refresh_id, symbol, f"valuation failed: {self._describe(exc)}")
                failed += 1
            else:
                valued += 1
            left = len(symbols) - valued - failed
            self._report(refresh_id, "value", valued, failed, left)
        return valued

    def _fail(self, conn: sqlite3.Connection, refresh_id: int, symbol: str, reason: str) -> None:
        """Give ``symbol`` a refusal snapshot of ``reason`` with the price the store holds, and
        mark it failed."""
        logger.warning("%s: %s", symbol, reason)
        price, price_date = latest_price(conn, symbol)
        today = self._clock().date()
        result = refusal_result(
            symbol, reason, self._policy, today, price=price, price_date=price_date
        )
        with transaction(conn):
            insert_snapshot(conn, result, refresh_id, clock=self._clock)
            upsert_item(conn, refresh_id, symbol, "failed", reason, self._clock())

    def _stage(self, conn: sqlite3.Connection, refresh_id: int, stage: str, total: int) -> None:
        set_stage(conn, refresh_id, stage)
        self._report(refresh_id, stage, 0, 0, total)

    def _report(
        self,
        refresh_id: int,
        stage: str,
        done: int,
        failed: int,
        remaining: int = 0,
        current: str | None = None,
    ) -> None:
        if self._on_progress is not None:
            self._on_progress(Progress(refresh_id, stage, done, failed, remaining, current))

    def _describe(self, exc: BaseException) -> str:
        """``<class>: <message>``, or the class alone, with the keys scrubbed."""
        text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        return scrub(text, self._secrets)
