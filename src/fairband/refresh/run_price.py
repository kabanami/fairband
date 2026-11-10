"""The price refresh: fresh quotes, then each company's latest snapshot at its new price (spec 6.2).

``Refresh.run("price")`` records the refresh and hands its stages to ``PriceRefresh``, on the run's
own connection. The symbols are the latest universe's admitted companies (``latest_companies``),
or, before any universe, every company with a snapshot. Each is listed ``pending``; one with no
snapshot is ``skipped`` at once ("no snapshot to reprice") and never quoted. Then:

- ``quotes``: the others' quotes, always called, never reused (the point is a fresh price), in
  batches of up to ``QUOTE_BATCH`` symbols: ``Fmp.quote`` asks ``batch-quote`` for several and
  ``quote`` for one. An account that does not serve ``batch-quote`` answers HTTP 402 or 403; that
  batch then takes one ``quote`` call a symbol. Each response is stored as the fetch stores one:
  its body scrubbed of the keys, with its ``quote_observations`` in one transaction (a batch's
  under no symbol, with ``{"symbols": "A,B"}`` as its params); a failed call as its status and
  scrubbed error. A symbol whose quote came is ``quoted``. Any other ``VendorError`` marks the
  call's symbols ``failed`` ("quote failed: <class>: <message>") and the stage goes on; a symbol
  the payload gives no row for is ``failed``, "no quote price". Progress counts symbols: after
  each call, those quoted are done.
- ``fx``: the pairs (``rates.pair_of``) of the currencies the quoted symbols' latest snapshots
  carry a rate in (``types.rated``: the ``currency`` and ``fx_rate`` intermediates; USD, none,
  and a currency named without a rate, a refusal for it, left out), quoted in batches of up to
  ``QUOTE_BATCH`` pairs, ``Fmp.quote`` as for the symbols (spec 2026-11-10 7.1). Each response is
  stored as a quote's is, under the endpoint ``fx-quote``, the pair as its symbol (none for a
  batch), with one ``fx-quote`` observation a pair (``fx_quote_observations``), the pair's close
  on the quote's date that ``rates.rates_for`` reads with the pair's history. A pair whose call
  fails or whose row is missing is logged and marks no symbol failed. Progress counts pairs. The
  stage leaves each pair's quote by currency for the reprice.
- ``reprice``: for each quoted symbol, one at a time, ``reprice`` of its latest snapshot at the new
  price and the quote's date, and ``insert_snapshot`` under this refresh; the symbol is
  ``repriced``. The value, levels, validity and every input but the price stay; the price input
  becomes the quote (its date and its row's stamps), and the designation, the price-dependent
  intermediates and the long-runway flag follow the price. A row in another currency reprices
  at its pair's quote, its rate and the quote's date (spec 2026-11-10 7.2): its USD value and
  levels move with the rate and ``fx-stale`` follows the rate's date; at the rate it holds, with
  ``fx-stale`` once that rate is older than ``fx_stale_days``, when its pair's quote failed or
  gave a price that is not positive and finite. A refusal takes the new price, its date and the
  price input only, except a growth-route refusal that carries ``revenue_path`` (refused for its
  target margin or for a value not positive), which also recomputes the margin the price needs,
  and a Start-up refusal, which moves its market cap with the price (the one it read × the new
  price ÷ the price it was read at, each in the reporting currency), recomputes its requirement
  at it and re-reads ``below-net-cash``. A snapshot valued under another policy version is
  ``failed``, "policy changed: run a revalue":
  its levels come from that policy. One valued under other
  settings (its settings hash unlike the run's, spec 2026-11-04 8.4) is ``failed``, "settings
  changed: run a revalue": its value and levels come from those settings. One valued under
  another method version is ``failed``, "method changed: run a revalue": its value is the old
  method's, and a rebuild at the price would carry it. The checks run in that order, so a
  snapshot unlike the run on several counts reads the first. A revalue writes the current
  versions and hash. An exception (``reprice`` refuses a price that is not positive and finite)
  is ``failed``, "reprice failed: <class>: <message>". In the repriced snapshot's transaction,
  ``multiples.log_snapshot`` logs its multiples at the quote's price as of the quote's date, the
  day's row replaced by a later reprice of the same day (spec 2026-11-06 Tier 2, 13.7), and
  ``reviews.reprice_review`` reprices the company's current review on the snapshot repriced, if
  it has one, at the same quote and writes it on the new snapshot (spec 2026-11-06 Tier 2, 10.5);
  a review that cannot be repriced becomes a refusal review and the snapshot stands.
- ``done``: the totals, and the calibration ``{"total", "repriced", "failed", "skipped"}`` saved
  with the record.

A failed or skipped symbol keeps the snapshot it had: no new row. A cancel, read before each call
and each symbol, ends the run ``cancelled`` with no further stage; the quotes stored stay. An HTTP
429 stops the quotes as it stops a full refresh's fetch: the call's symbols are ``failed``
("quote incomplete: rate limited"), those never reached stay ``pending``, those quoted are still
repriced, with no ``fx`` stage, and the run ends ``failed``, "rate limited by FMP: stopped after
<n> companies", n counting the symbols quoted or failed.
"""

import logging
import math
import sqlite3
import threading
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from http import HTTPStatus
from typing import Any

from fairband.engine import METHOD_VERSION
from fairband.engine.route import reprice
from fairband.engine.types import money_of, rated
from fairband.policy import Policy
from fairband.refresh.fetch import unusable
from fairband.refresh.rates import FX_QUOTE, foreign_currencies, pair_of
from fairband.refresh.reviews import reprice_review
from fairband.store.companies import latest_companies
from fairband.store.db import transaction
from fairband.store.multiples import log_snapshot
from fairband.store.observations import ObservationRow, insert_observations
from fairband.store.refreshes import Finished, set_stage, upsert_item
from fairband.store.snapshots import SnapshotRow, insert_snapshot, latest_snapshots
from fairband.store.vendor import record_response
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorError
from fairband.vendors.normalize_fmp import fx_quote_observations, quote_observations
from fairband.vendors.scrub import scrub

logger = logging.getLogger("fairband.refresh")

type Finish = tuple[Finished, str | None, dict[str, Any] | None]  # status, message, calibration
type Report = Callable[[str, int, int, int], None]  # stage, done, failed, remaining

QUOTE_BATCH = 100  # symbols a batch-quote call asks for
NO_SNAPSHOT = "no snapshot to reprice"
NO_QUOTE = "no quote price"
POLICY_CHANGED = "policy changed: run a revalue"
SETTINGS_CHANGED = "settings changed: run a revalue"
METHOD_CHANGED = "method changed: run a revalue"
RATE_LIMITED = "quote incomplete: rate limited"
_NO_BATCH = (HTTPStatus.PAYMENT_REQUIRED, HTTPStatus.FORBIDDEN)  # the plan serves no batch-quote
_PENDING = 0  # the response id the observations carry until their response is recorded


def rate_limited(provider: str, reached: int) -> str:
    """The message of a run a 429 stopped after ``reached`` companies."""
    noun = "company" if reached == 1 else "companies"
    return f"rate limited by {provider}: stopped after {reached} {noun}"


@dataclass(frozen=True)
class _Kind:
    """What a quote call asks for: the endpoint it is stored under when it asks for one symbol and
    for several, and the normalizer of each symbol's rows."""

    one: str
    several: str
    observe: Callable[[Any, str, int, datetime, datetime], list[ObservationRow]]


_SYMBOLS = _Kind("quote", "batch-quote", quote_observations)
_PAIRS = _Kind(FX_QUOTE, FX_QUOTE, fx_quote_observations)


@dataclass(frozen=True)
class _Quote:
    """A quote's price and date, and its price row's observation and entry stamps."""

    price: float
    as_of: date
    observed_at: datetime
    entered_at: datetime


@dataclass(frozen=True)
class _Quoted:
    """What the quotes stage left: each quoted symbol's quote, how many failed, and whether a
    429 stopped it."""

    quotes: dict[str, _Quote]
    failed: int
    limited: bool


class PriceRefresh:
    """The stages of one price refresh (see the module docstring). ``describe`` names an
    exception with the keys scrubbed; ``report`` gets the stage and its counts."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        fmp: Fmp,
        refresh_id: int,
        policy: Policy,
        clock: Callable[[], datetime],
        cancel: threading.Event,
        describe: Callable[[BaseException], str],
        secrets: Sequence[str],
        report: Report,
    ) -> None:
        self._conn = conn
        self._fmp = fmp
        self._id = refresh_id
        self._policy = policy
        self._clock = clock
        self._cancel = cancel
        self._describe = describe
        self._secrets = tuple(secrets)
        self._report = report

    def run(self) -> Finish:
        """The stages; the status, message and calibration to finish the record with."""
        conn = self._conn
        snapshots = {s.symbol: s for s in latest_snapshots(conn)}
        symbols = self._symbols(snapshots)
        quotable = [symbol for symbol in symbols if symbol in snapshots]
        with transaction(conn):
            for symbol in symbols:
                if symbol in snapshots:
                    upsert_item(conn, self._id, symbol, "pending", None, self._clock())
                else:
                    upsert_item(conn, self._id, symbol, "skipped", NO_SNAPSHOT, self._clock())
        quoted = self._quote_stage(quotable)
        if quoted.limited:
            self._reprice_stage(quoted.quotes, snapshots, {})
            return "failed", rate_limited("FMP", len(quoted.quotes) + quoted.failed), None
        if self._cancel.is_set():
            return "cancelled", None, None
        fx = self._fx_stage(quoted.quotes, snapshots)
        repriced = self._reprice_stage(quoted.quotes, snapshots, fx)
        if repriced is None:
            return "cancelled", None, None
        failed = quoted.failed + len(quoted.quotes) - repriced
        set_stage(conn, self._id, "done")
        self._report("done", repriced, failed, 0)
        calibration = {
            "total": len(symbols),
            "repriced": repriced,
            "failed": failed,
            "skipped": len(symbols) - len(quotable),
        }
        return "done", None, calibration

    def _symbols(self, snapshots: Mapping[str, SnapshotRow]) -> list[str]:
        """The latest universe's admitted companies; before any universe, every company with a
        snapshot (as the screen lists them)."""
        admitted = latest_companies(self._conn)
        if admitted or latest_companies(self._conn, eligible_only=False):
            return [company.symbol for company in admitted]
        return list(snapshots)

    def _quote_stage(self, symbols: Sequence[str]) -> _Quoted:
        """Quote ``symbols`` until all are quoted or failed, a cancel or a 429."""
        self._stage("quotes", len(symbols))
        starts = range(0, len(symbols), QUOTE_BATCH)
        calls = deque(list(symbols[start : start + QUOTE_BATCH]) for start in starts)
        quotes: dict[str, _Quote] = {}
        failed = 0
        limited = False
        while calls and not limited and not self._cancel.is_set():
            group = calls.popleft()
            outcome = self._call(group)
            if isinstance(outcome, VendorError) and len(group) > 1 and outcome.status in _NO_BATCH:
                calls.extendleft([symbol] for symbol in reversed(group))  # one call a symbol
                continue
            if isinstance(outcome, VendorError):
                limited = outcome.status == HTTPStatus.TOO_MANY_REQUESTS
                reason = RATE_LIMITED if limited else f"quote failed: {self._describe(outcome)}"
                for symbol in group:
                    self._fail(symbol, reason)
                failed += len(group)
            else:
                for symbol in group:
                    quote = outcome.get(symbol)
                    if quote is None:
                        self._fail(symbol, NO_QUOTE)
                        failed += 1
                    else:
                        upsert_item(self._conn, self._id, symbol, "quoted", None, self._clock())
                        quotes[symbol] = quote
            self._report("quotes", len(quotes), failed, len(symbols) - len(quotes) - failed)
        return _Quoted(quotes, failed, limited)

    def _fx_stage(
        self, quotes: Mapping[str, _Quote], snapshots: Mapping[str, SnapshotRow]
    ) -> dict[str, _Quote]:
        """Quote the pairs of the currencies the quoted symbols' latest snapshots carry a rate in,
        until all are quoted or failed or a cancel; each pair's quote by currency. A snapshot that
        names its currency with no rate, refused for it, quotes no pair: it is never read as
        rated."""
        results = (snapshots[symbol].result for symbol in quotes)
        named = (money_of(result)[1] for result in results if rated(result))
        pairs = {pair_of(currency): currency for currency in foreign_currencies(named)}
        self._stage("fx", len(pairs))
        names = list(pairs)
        rates: dict[str, _Quote] = {}
        failed = 0
        for start in range(0, len(names), QUOTE_BATCH):
            if self._cancel.is_set():
                break
            group = names[start : start + QUOTE_BATCH]
            outcome = self._call(group, _PAIRS)
            if isinstance(outcome, VendorError):
                logger.warning("%s: quote failed: %s", ",".join(group), self._describe(outcome))
                failed += len(group)
            else:
                for pair in group:
                    quote = outcome.get(pair)
                    if quote is None:
                        logger.warning("%s: %s", pair, NO_QUOTE)
                        failed += 1
                    else:
                        rates[pairs[pair]] = quote
            self._report("fx", len(rates), failed, len(names) - len(rates) - failed)
        return rates

    def _call(
        self, group: list[str], kind: _Kind = _SYMBOLS
    ) -> dict[str, _Quote | None] | VendorError:
        """One quote call for ``group``, stored; each symbol's quote, or the call's error."""
        if len(group) == 1:
            endpoint, params, symbol = kind.one, {"symbol": group[0]}, group[0]
        else:
            endpoint, params, symbol = kind.several, {"symbols": ",".join(group)}, None
        now = self._clock()
        try:
            response = self._fmp.quote(group)  # outside any transaction
        except VendorError as exc:
            message = scrub(str(exc), self._secrets)
            record_response(
                self._conn, "fmp", endpoint, params, symbol, exc.status, None, message, now
            )
            return exc
        observed = response.observed_at
        rows = {s: kind.observe(response.json, s, _PENDING, observed, now) for s in group}
        payload = scrub(response.text, self._secrets)
        error = None if any(rows.values()) else unusable(payload)
        with transaction(self._conn):
            response_id = record_response(
                self._conn,
                "fmp",
                endpoint,
                params,
                symbol,
                response.status,
                payload,
                error,
                observed,
            )
            insert_observations(
                self._conn,
                [replace(row, response_id=response_id) for found in rows.values() for row in found],
            )
        return {s: _price(found, observed.date()) for s, found in rows.items()}

    def _reprice_stage(
        self,
        quotes: Mapping[str, _Quote],
        snapshots: Mapping[str, SnapshotRow],
        fx: Mapping[str, _Quote],
    ) -> int | None:
        """Reprice each quoted symbol's latest snapshot; the number repriced, or ``None`` when a
        cancel stopped the stage. ``fx`` holds the pairs' quotes by currency (the ``fx``
        stage's): a snapshot in a currency with one reprices at its rate, with its review."""
        self._stage("reprice", len(quotes))
        repriced = failed = 0
        for symbol, quote in quotes.items():
            if self._cancel.is_set():
                return None
            result = snapshots[symbol].result
            reason = None
            if result.policy_version != self._policy.version:
                reason = POLICY_CHANGED
            elif result.settings_hash != self._policy.settings_hash:
                reason = SETTINGS_CHANGED
            elif result.method_version != METHOD_VERSION:
                reason = METHOD_CHANGED
            else:
                pair = fx.get(money_of(result)[1]) if rated(result) else None
                if pair is not None and not (math.isfinite(pair.price) and pair.price > 0):
                    pair = None  # a quote that is no rate: the snapshot's rate stands
                rate = None if pair is None else pair.price
                rate_date = None if pair is None else pair.as_of
                rate_seen = None if pair is None else pair.observed_at
                try:
                    new = reprice(
                        result,
                        quote.price,
                        quote.as_of,
                        self._policy,
                        fx_rate=rate,
                        fx_date=rate_date,
                        fx_observed_at=rate_seen,
                        observed_at=quote.observed_at,
                        entered_at=quote.entered_at,
                    )
                    with transaction(self._conn):
                        snapshot_id = insert_snapshot(self._conn, new, self._id, clock=self._clock)
                        log_snapshot(self._conn, new, snapshot_id, self._id, self._clock())
                        reprice_review(
                            self._conn,
                            symbol,
                            snapshot_id,
                            quote.price,
                            quote.as_of,
                            self._policy,
                            self._id,
                            self._clock,
                            observed_at=quote.observed_at,
                            entered_at=quote.entered_at,
                            repriced=snapshots[symbol].id,
                            fx_rate=rate,
                            fx_date=rate_date,
                            fx_observed_at=rate_seen,
                        )
                        upsert_item(self._conn, self._id, symbol, "repriced", None, self._clock())
                except Exception as exc:  # noqa: BLE001 - a symbol's failure is its own
                    reason = f"reprice failed: {self._describe(exc)}"
            if reason is None:
                repriced += 1
            else:
                self._fail(symbol, reason)
                failed += 1
            self._report("reprice", repriced, failed, len(quotes) - repriced - failed)
        return repriced

    def _fail(self, symbol: str, reason: str) -> None:
        """Mark ``symbol`` failed; its snapshot stays as it was."""
        logger.warning("%s: %s", symbol, reason)
        upsert_item(self._conn, self._id, symbol, "failed", reason, self._clock())

    def _stage(self, stage: str, total: int) -> None:
        set_stage(self._conn, self._id, stage)
        self._report(stage, 0, 0, total)


def _price(rows: Sequence[ObservationRow], observed: date) -> _Quote | None:
    """The quote's price and its date (the quote's own, else the day it was observed), with the
    price row's stamps; ``None`` without a price."""
    row = next((r for r in rows if r.field == "price" and r.value is not None), None)
    if row is None or row.value is None:
        return None
    return _Quote(float(row.value), row.as_of or observed, row.observed_at, row.entered_at)
