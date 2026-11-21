"""The exchange rates (spec 2026-11-10, 7.1): each reporting currency's daily closes against USD,
fetched in a refresh's ``rates`` stage, and the rate of a currency at a date.

The rate of a currency is FMP's close of the pair ``USD<code>`` (``pair_of``), in units of the
currency per USD, so a figure in the currency is ÷ the rate to USD and × the rate from it. USD's
rate is 1 on every day, and USD fetches nothing.

``fetch_rates`` makes one ``historical-price-eod/light`` call per currency, from
``refresh.fx_history_years`` years before ``now``, and stores the answer as ``fetch_company``
stores a response: endpoint ``fx-history`` (``FX_HISTORY``), the pair as the symbol, the body
scrubbed of the keys, whole and with no rows, the closes left in the payload; usable when it holds
a close. It reuses the newest usable answer observed within ``refresh.reuse_hours``, matched by
provider, endpoint and the pair alone (the ``from`` date changes daily, as the price history's
does, and is left out of the stored params), unless ``force``. A vendor error is stored with its
status and scrubbed message; a 429 stops the loop.

The price refresh stores each pair's quote as an observation (dataset ``fx-quote``, ``FX_QUOTE``,
under the pair as the symbol, period and as-of the quote's date). ``rates_for`` reads a currency's
series: the closes of its pair's latest usable history merged with every stored quote of the pair,
a quote winning on its date, the dates a quote supplied kept (``FxSeries.quoted``). ``FxSeries.at``
reads the last close at or before a date, stale when it is more than ``fx_stale_days`` before it,
and says whether a quote supplied it (``Rate.quoted``), so the rate's input names the source the
close came from.
"""

import bisect
import json
import re
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import partial
from http import HTTPStatus

from fairband.policy import Policy
from fairband.refresh.fetch import _Call, _log_failure, _store, _years_before
from fairband.store.observations import observations_for
from fairband.store.vendor import latest_response, record_response, response_payload
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorError
from fairband.vendors.normalize_fmp import fx_closes
from fairband.vendors.scrub import scrub

FX_HISTORY = "fx-history"  # the endpoint name the fetch stores the pair's history under
FX_QUOTE = "fx-quote"  # the price refresh's pair quotes
NO_RATE = "no exchange rate for {code}"

_USD = "USD"
_CODE = re.compile(r"[A-Z]{3}")
_DEFINED = datetime.min.replace(tzinfo=UTC)  # USD's rate is a definition, observed at no time


def pair_of(currency: str) -> str:
    """The FMP pair of a currency, ``USD`` and the code (``SEK`` → ``USDSEK``). Raises
    ``ValueError`` for USD, which has no pair, and for a code that is not three upper-case
    letters."""
    if currency == _USD or not _CODE.fullmatch(currency):
        raise ValueError(f"no exchange-rate pair for the currency {currency!r}")
    return _USD + currency


@dataclass(frozen=True)
class Rate:
    """A currency's rate at a date."""

    rate: float  # units of the currency per USD
    date: date  # the close's date
    observed_at: datetime
    stale: bool  # the close is more than fx_stale_days before the date asked for
    quoted: bool = False  # a stored pair quote supplied the close, not the pair's history


@dataclass(frozen=True)
class FxSeries:
    """A currency's daily closes against USD, and when the store observed them (the newest of the
    history and the quotes read), with the dates whose close is a stored pair quote. USD's series
    holds no close: its rate is 1 on every day."""

    currency: str
    closes: tuple[tuple[date, float], ...]  # oldest first; the history's and the pair's quotes
    observed_at: datetime
    quoted: frozenset[date] = frozenset()  # the dates a stored pair quote supplied

    def at(self, day: date, stale_days: int) -> Rate | None:
        """The last close at or before ``day``; None without one. ``stale`` when that close is
        more than ``stale_days`` before ``day``; ``quoted`` when a stored pair quote supplied it."""
        if self.currency == _USD:
            return Rate(1.0, day, self.observed_at, False)
        index = bisect.bisect_right(self.closes, day, key=lambda close: close[0])
        if index == 0:
            return None
        when, rate = self.closes[index - 1]
        stale = (day - when).days > stale_days
        return Rate(rate, when, self.observed_at, stale, when in self.quoted)


def rates_for(conn: sqlite3.Connection, currency: str) -> FxSeries | None:
    """The latest usable fx-history response of the pair, its closes merged with every stored
    fx-quote observation of the pair, the dates the quotes supplied kept; None without a usable
    history (a code that names no pair has none). USD gives a series whose ``at`` is always 1.0 on
    the day asked, never stale."""
    if currency == _USD:
        return FxSeries(_USD, (), _DEFINED)
    if not _CODE.fullmatch(currency):
        return None
    pair = pair_of(currency)
    response = latest_response(conn, "fmp", FX_HISTORY, pair, {"symbol": pair})
    text = None if response is None else response_payload(conn, response.id)
    if response is None or text is None:
        return None
    try:
        closes = dict(fx_closes(json.loads(text)))
    except ValueError:
        return None
    if not closes:
        return None
    observed = response.observed_at
    quoted: set[date] = set()
    for row in observations_for(conn, pair, FX_QUOTE):
        if row.field != "price" or row.period is None or row.value is None or row.value <= 0:
            continue
        closes[row.period] = float(row.value)
        quoted.add(row.period)
        observed = max(observed, row.observed_at)
    return FxSeries(currency, tuple(sorted(closes.items())), observed, frozenset(quoted))


def currencies_of(conn: sqlite3.Connection, symbols: Sequence[str]) -> tuple[str, ...]:
    """The distinct reporting currencies of ``symbols``' newest annual income statements (the
    newest ``income-annual`` fact's ``currency`` per symbol), USD and None left out, sorted; a
    code that names no pair is left out too."""
    found = []
    for symbol in symbols:
        row = conn.execute(
            "SELECT currency FROM facts WHERE symbol = ? AND dataset = 'income-annual'"
            " ORDER BY period_end DESC, response_id DESC, id DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        found.append(None if row is None else row["currency"])
    return foreign_currencies(found)


def foreign_currencies(codes: Iterable[object]) -> tuple[str, ...]:
    """The distinct codes among ``codes`` that have a pair (``pair_of``), sorted: USD, None and
    anything that is not three upper-case letters left out."""
    named = {code for code in codes if isinstance(code, str) and _CODE.fullmatch(code)}
    return tuple(sorted(named - {_USD}))


@dataclass(frozen=True)
class RatesOutcome:
    """What one ``fetch_rates`` did, by currency, in the order given."""

    fetched: tuple[str, ...]  # the currencies whose pair was fetched or reused
    calls: int
    reused: int
    failed: tuple[str, ...]  # the currencies whose call failed or gave no close
    rate_limited: bool


def fetch_rates(
    conn: sqlite3.Connection,
    fmp: Fmp,
    currencies: Sequence[str],
    policy: Policy,
    now: datetime,
    secrets: Sequence[str],
    force: bool = False,
) -> RatesOutcome:
    """One fx-history call per currency, from ``now - fx_history_years`` years; reused within
    ``reuse_hours`` by provider, endpoint and the pair alone (the ``from`` parameter changes daily,
    as the price history's does); stored whole as the fetch stores a response (``fetch._store``
    with a call whose symbol is the pair), no rows, usable when it gives a close. A 429 stops the
    loop and sets ``rate_limited``. Never raises for a vendor error.

    ``now`` judges freshness and stamps a failed call's row; ``secrets`` are the vendor keys,
    scrubbed from every stored text. Raises ``ValueError`` for a currency with no pair (USD
    among them)."""
    window = timedelta(hours=policy.refresh.reuse_hours)
    start = _years_before(now.date(), policy.refresh.fx_history_years)
    fetched: list[str] = []
    failed: list[str] = []
    calls = reused = 0
    rate_limited = False
    for currency in currencies:
        pair = pair_of(currency)
        send = partial(fmp.fx_history, pair, start)
        call = _Call("fmp", FX_HISTORY, {"symbol": pair}, send)
        latest = latest_response(conn, "fmp", FX_HISTORY, pair, call.params)
        if not force and latest is not None and now - latest.observed_at < window:
            reused += 1
            fetched.append(currency)
            continue
        calls += 1
        try:
            response = send()
        except VendorError as exc:
            message = scrub(str(exc), secrets)
            record_response(
                conn, "fmp", FX_HISTORY, call.params, pair, exc.status, None, message, now
            )
            _log_failure(pair, call, message)
            failed.append(currency)
            if exc.status == HTTPStatus.TOO_MANY_REQUESTS:
                rate_limited = True
                break
            continue
        error = _store(conn, call, pair, response, now, secrets)
        if error is None:
            fetched.append(currency)
        else:
            _log_failure(pair, call, error)
            failed.append(currency)
    return RatesOutcome(tuple(fetched), calls, reused, tuple(failed), rate_limited)
