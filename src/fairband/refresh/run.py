"""The refresh runner: one refresh record, its stages and each company's progress (spec 6.2).

``Refresh.run(kind, symbols)`` records the policy and starts a ``running`` refresh (while another
runs, ``create_refresh`` raises ``RefreshRunning``). A full refresh first runs:

- ``universe``: ``build_universe`` records the screener's universe, called afresh or reused within
  ``reuse_hours``, under the refresh; the admitted symbols are the refresh's symbols. A
  ``VendorError`` or an empty screener (``ValueError``) ends the run ``failed`` and is raised again;
  a universe that admits no company ends it ``failed``, "universe admitted no company", before
  any fetch.

A scoped refresh takes the symbols it is given. Both then list each symbol ``pending`` and run:

- ``fetch``: ``fetch_company`` for each symbol on a daemon thread of its own, with a connection of
  its own from ``conn_factory``. At most ``policy.refresh.workers`` symbols are in flight, and the
  run starts the next only after it has recorded a finished one. A symbol becomes ``fetching``,
  then ``fetched``, or ``failed`` with the fetch's error and a refusal snapshot of that reason
  ("data fetch failed: <endpoints>") that carries the price the store holds. The stage ends with
  one INFO line on the FMP limiter's share of it: "FMP pace: waited <s> s over <n> calls, <h>
  holds".
- ``deciles`` (full only): ``deciles_for_universe`` over every admitted symbol, from the statements
  the store holds, saved under the refresh (spec 6.6). When they rank no company on growth, the run
  ends ``failed``, "deciles rank no company", and saves none: empty deciles would put every later
  company in decile 1, and the last good universe's stay the ones a scoped refresh uses.
- ``backfill``: ``backfill_statement_facts`` on the run's own connection writes the facts of the
  statement lines the normalizer gained after their responses were stored, from the stored
  payloads (spec 2026-11-03 section 11): the fetch reuses a response observed within
  ``reuse_hours`` without a call, so it may predate a line. The stage reports its start alone.
- ``value``: on the run's own connection, one fetched symbol at a time: ``build_inputs`` and
  ``value_company`` with the latest stored deciles (a full refresh's own; assembly classifies the
  company's peers on them), ``insert_snapshot``; the symbol is ``valued``. Without stored deciles the snapshot is the refusal "no universe deciles
  yet" (spec 6.6). In the snapshot's transaction, ``multiples.log_snapshot`` logs its multiples
  as of its price date when it carries a price (spec 2026-11-06 Tier 2, 13.7), and
  ``reviews.follow_snapshot`` follows it with a review on the same inputs when the company holds
  an applied override, after dropping a period-tied one its new inputs no longer bear out (spec
  2026-11-06 Tier 2, 10.5); a review the engine cannot compute becomes a refusal review and the
  snapshot stands.
- ``done``: the run's totals. A full refresh saves its ``calibration`` with the record (goal 7).

Every kind but a revalue fetches, so without an FMP client (the server's worker without a key)
``run`` refuses it with a ``ValueError`` naming the keys file, before the record exists.

A revalue takes no symbols, makes no vendor call and needs no FMP client (calibration spec 5.9): it
lists the latest universe's admitted companies (``latest_companies``) ``pending``, in symbol order,
or, before any universe, every company with a snapshot (``latest_snapshots``), as the price
refresh does; then it runs the ``backfill`` and the ``value`` stage on the facts the store holds,
with the latest stored deciles, then ``done``. A company the store holds no facts for gets the
engine's refusal. It saves its ``calibration`` like a full refresh, with no listing left out: it
builds no universe.

A symbol's failure never stops the run: an exception from its fetch, assembly or valuation gives it
a refusal snapshot ("data fetch failed: <class>: <message>" or "valuation failed: <class>:
<message>", the keys scrubbed), marks it ``failed`` and is logged as a warning. A company with an
applied override gets that refusal as its review too (``reviews.review_refusal``). The refusal
logs no multiples: its price is a stored quote whose day the log already holds.

The run stops early on two events. A cancel is read before each symbol starts, in both stages; the
symbols in flight finish and the run ends ``cancelled``, with no further stage: a fetched symbol
keeps its stored responses, which the next run reuses within ``reuse_hours``, and a valued one its
snapshot. So a full refresh cancelled while it fetches saves no deciles and values nothing, and the
next one, a new record over a universe built again, fetches only the companies not fetched within
``reuse_hours``: it continues. A cancel that lands while the deciles are computed still saves them
(they rank the whole universe); the value stage then values nothing. An HTTP 429 (``FetchOutcome.rate_limited``) ends the fetching the
same way; the symbol it hit gets the refusal "data fetch incomplete: rate limited" and is
``failed`` (spec 6.2: a failed fetch gets a row), the symbols never reached stay ``pending`` with
no snapshot, the symbols fetched are still valued (on the stored deciles: a full refresh saves
none), and the run ends ``failed`` with "rate limited by <provider>: stopped after <n> companies",
n counting the symbols fetched or failed; the backfill runs before that value stage too. An
exception outside a symbol's work ends the run ``failed`` with its class and message, and is
raised again.

Why daemon threads: an exception in the fetch stage (a second Ctrl-C in the command) must not wait
for the fetches in flight, which on a stalled vendor run to minutes (13 FMP and 2 GuruFocus calls,
each up to ``deadline_s`` and an FMP call longer by its waits in the limiter). The run gives them up
at once: their symbols go back to ``pending``, the run ends ``failed`` and the exception propagates.
A ``ThreadPoolExecutor``'s workers are joined when the interpreter exits, even after
``shutdown(wait=False)``, and ending the command with ``os._exit`` would skip its own cleanup (the
signal handler, the clients, the output); a daemon thread is simply not joined. What a given-up
fetch still stores is a response like any other, reused by the next run; ``fetches_in_flight``
counts the fetch threads not ended, so a long-lived caller (the server's worker) can wait for them
before it starts another run.

A price refresh takes no symbols; ``run_price.PriceRefresh`` runs its stages (``quotes``,
``reprice``, ``done``) on the run's connection, and its module docstring says how. It values
nothing and runs no backfill.

The record carries the policy's version and its settings hash (spec 2026-11-04, 8.4): the run
values under the policy it was built with, the effective one its caller read when it started.

``on_progress`` gets a ``Progress`` at each stage change and after each symbol, and ``on_started``
the refresh id once the record exists; both run on the thread that called ``run``. ``close`` closes
the clients the run was built with; the server's worker calls it before its next run.
"""

import logging
import queue
import sqlite3
import threading
from collections import Counter, deque
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any, Literal

from fairband.config import MissingKey
from fairband.engine import METHOD_VERSION
from fairband.engine.route import refusal_result, value_company
from fairband.engine.types import PHASE_NUMBER
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.refresh.backfill import backfill_statement_facts
from fairband.refresh.deciles import deciles_for_universe
from fairband.refresh.fetch import FetchOutcome, fetch_company, provider_of
from fairband.refresh.inputs import build_inputs, latest_price
from fairband.refresh.reviews import follow_snapshot, review_refusal
from fairband.refresh.run_price import PriceRefresh, rate_limited
from fairband.refresh.universe import build_universe
from fairband.store.companies import latest_companies
from fairband.store.db import transaction
from fairband.store.multiples import log_snapshot
from fairband.store.policy import record_policy
from fairband.store.refreshes import (
    Finished,
    create_refresh,
    finish_refresh,
    items,
    latest_deciles,
    save_deciles,
    set_stage,
    upsert_item,
)
from fairband.store.snapshots import (
    SnapshotRow,
    insert_snapshot,
    latest_snapshots,
    refresh_snapshots,
)
from fairband.vendors.fmp import Fmp
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.scrub import scrub

logger = logging.getLogger("fairband.refresh")

type Kind = Literal["full", "price", "scoped", "revalue"]
type _Result = tuple[str, FetchOutcome | BaseException]  # a symbol's fetch, as its thread ended
type _Finish = tuple[Finished, str | None, dict[str, Any] | None]  # status, message, calibration

KINDS: tuple[Kind, ...] = ("full", "price", "scoped", "revalue")
UNCLASSIFIED = "unclassified"  # the calibration's name for a company without a phase
NO_COMPANY_ADMITTED = "universe admitted no company"
NO_COMPANY_RANKED = "deciles rank no company"
_PROVIDER_NAMES = {"fmp": "FMP", "gf": "GuruFocus"}
_RATE_LIMITED = "data fetch incomplete: rate limited"


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
    keys, scrubbed from what the fetch stores and from every message the run writes. ``close``
    closes the run's clients, when its caller hands it the clients to close."""

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
        close: Callable[[], None] | None = None,
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
        self._close = close
        self._in_flight = 0
        self._in_flight_lock = threading.Lock()

    def run(
        self,
        kind: Kind,
        symbols: Sequence[str] | None = None,
        on_started: Callable[[int], None] | None = None,
    ) -> int:
        """Run a refresh of ``kind`` and return its id. Raises ``ValueError`` without an FMP
        client for a kind that fetches (all but a revalue), with ``MissingKey``'s text, and for a
        scoped refresh without symbols or another kind with them, all before any work."""
        fmp = self._fmp
        if kind != "revalue" and fmp is None:
            raise ValueError(str(MissingKey("fmp")))
        names: list[str] | None = None
        if kind == "scoped":
            if not symbols:
                raise ValueError("a scoped refresh needs symbols")
            names = list(dict.fromkeys(symbols))
        elif symbols:
            raise ValueError(f"a {kind} refresh takes no symbols")
        with closing(self._conn_factory()) as conn:
            record_policy(conn, self._policy, self._clock())
            refresh_id = create_refresh(
                conn,
                kind,
                names,
                self._policy.version,
                METHOD_VERSION,
                self._clock(),
                self._policy.settings_hash,
            )
            try:
                if on_started is not None:
                    on_started(refresh_id)
                if kind == "revalue":
                    status, message, counts = self._revalue(conn, refresh_id)
                else:
                    assert fmp is not None  # refused above, before the record
                    if kind == "price":
                        status, message, counts = self._price(conn, fmp, refresh_id)
                    elif names is None:
                        status, message, counts = self._full(conn, fmp, refresh_id)
                    else:
                        status, message, counts = self._scoped(conn, fmp, refresh_id, names)
            except BaseException as exc:
                finish_refresh(conn, refresh_id, "failed", self._clock(), self.describe(exc))
                raise
            finish_refresh(conn, refresh_id, status, self._clock(), message, counts)
        return refresh_id

    def close(self) -> None:
        """Close the clients the run was built with, once; nothing when it was given none to
        close. The caller closes them only once the run and its fetches have ended."""
        close, self._close = self._close, None
        if close is not None:
            close()

    def fetches_in_flight(self) -> int:
        """The fetch threads not ended yet, those a stopped run gave up among them."""
        with self._in_flight_lock:
            return self._in_flight

    def describe(self, exc: BaseException) -> str:
        """``<class>: <message>``, or the class alone, with the keys scrubbed."""
        text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        return scrub(text, self._secrets)

    def _full(self, conn: sqlite3.Connection, fmp: Fmp, refresh_id: int) -> _Finish:
        """The stages of a full refresh; the status, message and calibration to finish it with."""
        self._stage(conn, refresh_id, "universe", 0)
        universe = build_universe(conn, fmp, self._policy, refresh_id, self._clock(), self._secrets)
        symbols = universe.admitted
        self._report(refresh_id, "universe", len(symbols), 0)
        if not symbols:
            return "failed", NO_COMPANY_ADMITTED, None
        fetched = self._fetch_pending(conn, fmp, refresh_id, symbols)
        stopped = self._stopped(conn, refresh_id, fetched)
        if stopped is not None:
            return stopped
        self._stage(conn, refresh_id, "deciles", len(symbols))
        deciles = deciles_for_universe(conn, symbols, refresh_id)
        if deciles.n_growth == 0:
            return "failed", NO_COMPANY_RANKED, None
        save_deciles(conn, refresh_id, deciles, self._clock())
        self._report(refresh_id, "deciles", len(symbols), 0)
        self._backfill(conn, refresh_id)
        valued = self._value_stage(conn, refresh_id, fetched.symbols)
        if valued is None:
            return "cancelled", None, None
        self._done(conn, refresh_id, fetched, valued)
        snapshots = refresh_snapshots(conn, refresh_id)
        return "done", None, calibration(universe.admitted, universe.excluded, snapshots)

    def _price(self, conn: sqlite3.Connection, fmp: Fmp, refresh_id: int) -> _Finish:
        """The stages of a price refresh (``run_price``)."""
        report = partial(self._report, refresh_id)
        return PriceRefresh(
            conn,
            fmp,
            refresh_id,
            self._policy,
            self._clock,
            self._cancel,
            self.describe,
            self._secrets,
            report,
        ).run()

    def _scoped(
        self, conn: sqlite3.Connection, fmp: Fmp, refresh_id: int, symbols: list[str]
    ) -> _Finish:
        """The stages of a scoped refresh; the status and message to finish it with."""
        fetched = self._fetch_pending(conn, fmp, refresh_id, symbols)
        stopped = self._stopped(conn, refresh_id, fetched)
        if stopped is not None:
            return stopped
        self._backfill(conn, refresh_id)
        valued = self._value_stage(conn, refresh_id, fetched.symbols)
        if valued is None:
            return "cancelled", None, None
        self._done(conn, refresh_id, fetched, valued)
        return "done", None, None

    def _revalue(self, conn: sqlite3.Connection, refresh_id: int) -> _Finish:
        """The stages of a revalue; the status, message and calibration to finish it with."""
        symbols = _revalue_symbols(conn)
        self._list_pending(conn, refresh_id, symbols)
        self._backfill(conn, refresh_id)
        valued = self._value_stage(conn, refresh_id, symbols)
        if valued is None:
            return "cancelled", None, None
        # The store's facts stand in for a fetch: every company counts as fetched.
        self._done(conn, refresh_id, _Fetched(symbols, 0, None), valued)
        snapshots = refresh_snapshots(conn, refresh_id)
        return "done", None, calibration(symbols, {}, snapshots)

    def _fetch_pending(
        self, conn: sqlite3.Connection, fmp: Fmp, refresh_id: int, symbols: Sequence[str]
    ) -> _Fetched:
        """List each symbol ``pending``, then fetch them."""
        self._list_pending(conn, refresh_id, symbols)
        return self._fetch_stage(conn, fmp, refresh_id, symbols)

    def _list_pending(
        self, conn: sqlite3.Connection, refresh_id: int, symbols: Sequence[str]
    ) -> None:
        with transaction(conn):
            for symbol in symbols:
                upsert_item(conn, refresh_id, symbol, "pending", None, self._clock())

    def _stopped(
        self, conn: sqlite3.Connection, refresh_id: int, fetched: _Fetched
    ) -> _Finish | None:
        """How the run ends when the fetch stage stopped early, else ``None``: after a 429 the
        symbols fetched are valued and the run fails; after a cancel it is cancelled."""
        if fetched.limited_by is not None:
            self._backfill(conn, refresh_id)
            self._value_stage(conn, refresh_id, fetched.symbols)
            reached = len(fetched.symbols) + fetched.failed
            return "failed", rate_limited(fetched.limited_by, reached), None
        if self._cancel.is_set():
            return "cancelled", None, None
        return None

    def _done(
        self, conn: sqlite3.Connection, refresh_id: int, fetched: _Fetched, valued: int
    ) -> None:
        set_stage(conn, refresh_id, "done")
        self._report(refresh_id, "done", valued, fetched.failed + len(fetched.symbols) - valued)

    def _fetch_stage(
        self, conn: sqlite3.Connection, fmp: Fmp, refresh_id: int, symbols: Sequence[str]
    ) -> _Fetched:
        """Fetch ``symbols`` until all are fetched, a cancel or a 429. An exception here gives up
        the fetches in flight and puts their symbols back to ``pending`` before it propagates."""
        self._stage(conn, refresh_id, "fetch", len(symbols))
        pace = fmp.limiter.totals()
        workers = self._policy.refresh.workers
        waiting = deque(symbols)
        running: list[str] = []  # in the order started
        finished: queue.Queue[_Result] = queue.Queue()
        fetched: list[str] = []
        failed = 0
        limited_by: str | None = None
        try:
            while True:
                while waiting and len(running) < workers:
                    if limited_by is not None or self._cancel.is_set():
                        break
                    symbol = waiting.popleft()
                    now = self._clock()
                    upsert_item(conn, refresh_id, symbol, "fetching", None, now)
                    self._start_fetch(fmp, symbol, now, finished)
                    running.append(symbol)
                if not running:
                    break
                symbol, result = finished.get()
                running.remove(symbol)
                reason: str | None
                if isinstance(result, Exception):
                    reason = f"data fetch failed: {self.describe(result)}"
                elif isinstance(result, BaseException):
                    raise result  # not the symbol's failure: SystemExit and the like
                elif result.rate_limited:
                    limited_by = limited_by or _PROVIDER_NAMES[provider_of(result.failed[-1])]
                    reason = _RATE_LIMITED
                else:
                    reason = result.error
                if reason is None:
                    upsert_item(conn, refresh_id, symbol, "fetched", None, self._clock())
                    fetched.append(symbol)
                else:
                    self._fail(conn, refresh_id, symbol, reason)
                    failed += 1
                left = len(symbols) - len(fetched) - failed
                current = running[0] if running else None
                self._report(refresh_id, "fetch", len(fetched), failed, left, current)
        except BaseException:
            # It reads, then writes, while the given-up fetches still write: a deferred
            # transaction could not upgrade its read (SQLITE_BUSY at once, no busy wait), so it
            # takes the write lock first.
            with transaction(conn, immediate=True):
                for item in items(conn, refresh_id):
                    if item.status == "fetching":
                        upsert_item(conn, refresh_id, item.symbol, "pending", None, self._clock())
            raise
        paced = fmp.limiter.totals().since(pace)
        logger.info(
            "FMP pace: waited %.1f s over %d calls, %d holds",
            paced.waited_s,
            paced.calls,
            paced.holds,
        )
        return _Fetched(tuple(fetched), failed, limited_by)

    def _start_fetch(
        self, fmp: Fmp, symbol: str, now: datetime, finished: queue.Queue[_Result]
    ) -> None:
        """Fetch ``symbol`` on a daemon thread of its own (module docstring), with a connection
        of its own; the outcome, or what the fetch raised, goes to ``finished``."""

        def fetch() -> None:
            try:
                with closing(self._conn_factory()) as conn:
                    outcome = fetch_company(
                        conn, fmp, self._gf, symbol, self._policy, now, self._secrets
                    )
            except BaseException as exc:  # noqa: BLE001 - handed to the run, which decides
                finished.put((symbol, exc))
            else:
                finished.put((symbol, outcome))
            finally:
                with self._in_flight_lock:
                    self._in_flight -= 1

        with self._in_flight_lock:
            self._in_flight += 1
        threading.Thread(target=fetch, name=f"fairband-fetch {symbol}", daemon=True).start()

    def _backfill(self, conn: sqlite3.Connection, refresh_id: int) -> None:
        """The ``backfill`` stage: the statement facts missing from the stored responses."""
        self._stage(conn, refresh_id, "backfill", 0)
        backfill_statement_facts(conn, self._clock())

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
                inputs = build_inputs(conn, symbol, self._policy, self._tax, today, deciles)
                result = value_company(inputs, deciles, self._policy, today)
                with transaction(conn):
                    snapshot_id = insert_snapshot(conn, result, refresh_id, clock=self._clock)
                    log_snapshot(conn, result, snapshot_id, refresh_id, self._clock())
                    follow_snapshot(
                        conn,
                        inputs,
                        result,
                        snapshot_id,
                        deciles,
                        self._policy,
                        today,
                        refresh_id,
                        self._clock,
                    )
                    upsert_item(conn, refresh_id, symbol, "valued", None, self._clock())
            except Exception as exc:  # noqa: BLE001 - a symbol's failure is its own
                self._fail(conn, refresh_id, symbol, f"valuation failed: {self.describe(exc)}")
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
            snapshot_id = insert_snapshot(conn, result, refresh_id, clock=self._clock)
            review_refusal(conn, result, snapshot_id, refresh_id, self._clock)
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


def _revalue_symbols(conn: sqlite3.Connection) -> tuple[str, ...]:
    """The latest universe's admitted companies; before any universe, every company with a
    snapshot (as the price refresh takes them), in symbol order."""
    admitted = latest_companies(conn)
    if admitted or latest_companies(conn, eligible_only=False):
        return tuple(company.symbol for company in admitted)
    return tuple(snapshot.symbol for snapshot in latest_snapshots(conn))


def calibration(
    admitted: Sequence[str], excluded: Mapping[str, int], snapshots: Sequence[SnapshotRow]
) -> dict[str, Any]:
    """A full refresh's or a revalue's counts (goal 7) over the snapshots it wrote, one per company
    of ``admitted``: the companies, those with a value, the refusals by reason, the phases
    (``unclassified`` for none), the companies flagged by a classifier check (``design.md`` 5.8: a
    non-empty ``phase.checks``), each flag code's count over every flag, and how many companies
    the universe admitted and the listings it left out by reason (``excluded``; none for a
    revalue). Numbers only: the record stores it as JSON."""
    phases = dict.fromkeys([*PHASE_NUMBER, UNCLASSIFIED], 0)
    refused: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    for snapshot in snapshots:
        phases[snapshot.phase or UNCLASSIFIED] += 1
        if snapshot.refusal is not None:
            refused[snapshot.refusal] += 1
        flags.update(snapshot.flags)
    return {
        "total": len(admitted),
        "valued": sum(1 for snapshot in snapshots if snapshot.value is not None),
        "refused": dict(refused),
        "phases": phases,
        "flagged": sum(1 for snapshot in snapshots if snapshot.result.phase.checks),
        "flags": dict(flags),
        "universe": {"admitted": len(admitted), "excluded": dict(excluded)},
    }
