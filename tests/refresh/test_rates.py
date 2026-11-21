"""The exchange rates (spec 2026-11-10, 7.1) against the fixture router and a migrated temporary
database: a currency's pair, a rate read at a date, the series the store holds for a currency (the
pair's daily closes and its quotes), the currencies of the fetched companies and the fetch of each
pair's closes. The router answers ``fx-history`` with the made-up USDSEK and USDTWD fixtures."""

import json
import sqlite3
from datetime import date, timedelta
from typing import Any

import pytest
from synthetic import NOW, bodies
from vendor_double import FIXTURES, FMP_KEY, Clients, Clock, Router

from fairband.policy import Policy
from fairband.refresh.rates import (
    FX_HISTORY,
    FX_QUOTE,
    NO_RATE,
    FxSeries,
    Rate,
    RatesOutcome,
    currencies_of,
    fetch_rates,
    pair_of,
    rates_for,
)
from fairband.store.facts import insert_facts
from fairband.store.observations import insert_observations
from fairband.store.vendor import record_response
from fairband.vendors.normalize_fmp import fx_quote_observations, statement_facts

QUARTER_ENDS = (date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30))


def fetch(
    conn: sqlite3.Connection,
    clients: Clients,
    policy: Policy,
    clock: Clock,
    currencies: tuple[str, ...] = ("SEK",),
    force: bool = False,
) -> RatesOutcome:
    return fetch_rates(conn, clients.fmp, currencies, policy, clock(), clients.secrets, force=force)


def store_pair_quote(conn: sqlite3.Connection, pair: str, price: float, day: date) -> None:
    """A pair's quote of ``day``, observed that day, as the price refresh stores one: the
    response, then its observation."""
    observed = NOW + timedelta(days=(day - NOW.date()).days)
    payload = [{"symbol": pair, "price": price, "timestamp": int(observed.timestamp())}]
    response_id = record_response(
        conn, "fmp", FX_QUOTE, {"symbol": pair}, pair, 200, json.dumps(payload), None, observed
    )
    insert_observations(conn, fx_quote_observations(payload, pair, response_id, observed, observed))


def store_income(conn: sqlite3.Connection, symbol: str, rows: list[dict[str, Any]]) -> None:
    """``rows`` as the fetch stores a company's annual income statements."""
    response_id = record_response(
        conn, "fmp", "income-annual", {"symbol": symbol}, symbol, 200, json.dumps(rows), None, NOW
    )
    insert_facts(conn, statement_facts(rows, symbol, "income-annual", response_id, NOW, NOW))


def stored_responses(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM vendor_responses WHERE endpoint = ? ORDER BY id", (FX_HISTORY,)
    ).fetchall()


def test_the_pair_of_a_currency() -> None:
    assert (pair_of("SEK"), pair_of("TWD")) == ("USDSEK", "USDTWD")
    for code in ("USD", "sek", "SE", "SEKK", "", "unknown"):
        with pytest.raises(ValueError, match="currency"):
            pair_of(code)
    assert NO_RATE.format(code="SEK") == "no exchange rate for SEK"


def test_at_reads_the_last_close_at_or_before_the_day() -> None:
    s = FxSeries("SEK", ((date(2026, 11, 1), 10.5), (date(2026, 11, 5), 10.6)), NOW)
    assert s.at(date(2026, 11, 5), 7) == Rate(10.6, date(2026, 11, 5), NOW, False)
    assert s.at(date(2026, 11, 4), 7) == Rate(10.5, date(2026, 11, 1), NOW, False)
    assert s.at(date(2026, 11, 10), 7) == Rate(10.6, date(2026, 11, 5), NOW, False)  # 5 days
    assert s.at(date(2026, 11, 12), 7) == Rate(10.6, date(2026, 11, 5), NOW, False)  # 7 days
    assert s.at(date(2026, 11, 13), 7) == Rate(10.6, date(2026, 11, 5), NOW, True)  # 8 days
    assert s.at(date(2026, 10, 31), 7) is None
    # Spec 11.2: a close of 2026-11-01 read for 2026-11-10 is stale (9 days).
    assert FxSeries("SEK", ((date(2026, 11, 1), 10.5),), NOW).at(date(2026, 11, 10), 7) == Rate(
        10.5, date(2026, 11, 1), NOW, True
    )


def test_a_series_reads_no_mean_of_several_days() -> None:
    """Spec 2026-11-19 7.1: the mean of the trailing periods' rates translated GuruFocus's EPS,
    which the engine no longer reads; a rate is read at one date."""
    assert not hasattr(FxSeries, "mean_at")


def test_usd_is_one_on_every_day(conn: sqlite3.Connection) -> None:
    usd = rates_for(conn, "USD")
    assert usd is not None and usd.currency == "USD"
    for day in (date(1990, 1, 1), date(2026, 11, 10)):
        assert usd.at(day, 7) == Rate(1.0, day, usd.observed_at, False)


def test_rates_for_merges_the_history_and_the_pair_quotes(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    assert rates_for(conn, "SEK") is None and rates_for(conn, "TWD") is None  # before any fetch
    assert rates_for(conn, "unknown") is None  # no pair
    assert fetch(conn, clients, policy, clock) == RatesOutcome(("SEK",), 1, 0, (), False)

    series = rates_for(conn, "SEK")
    assert series is not None
    assert (series.currency, series.observed_at) == ("SEK", NOW)
    assert series.closes[0] == (date(2025, 9, 30), 7.7) and len(series.closes) == 53
    assert [series.at(end, 7) for end in QUARTER_ENDS] == [
        Rate(rate, end, NOW, False) for rate, end in zip((7.8, 7.9, 8.1, 8.2), QUARTER_ENDS)
    ]
    assert series.at(date(2026, 11, 6), 7) == Rate(10.6, date(2026, 11, 5), NOW, False)
    assert rates_for(conn, "TWD") is None  # its pair was not fetched

    # A pair quote stored by a price refresh joins the closes; on a date the history holds, the
    # quote wins. A rate says whether a quote supplied its close, so its input names the source.
    store_pair_quote(conn, "USDSEK", 10.7, date(2026, 11, 6))
    store_pair_quote(conn, "USDSEK", 10.65, date(2026, 11, 2))
    later = NOW + timedelta(days=5)
    series = rates_for(conn, "SEK")
    assert series is not None and series.observed_at == later  # the newest of what it read
    assert series.quoted == frozenset({date(2026, 11, 6), date(2026, 11, 2)})
    assert series.at(date(2026, 11, 6), 7) == Rate(10.7, date(2026, 11, 6), later, False, True)
    assert series.at(date(2026, 11, 5), 7) == Rate(10.6, date(2026, 11, 5), later, False, False)
    assert series.at(date(2026, 11, 2), 7) == Rate(10.65, date(2026, 11, 2), later, False, True)
    assert series.at(date(2026, 11, 4), 7) == Rate(10.48, date(2026, 11, 4), later, False, False)
    assert len(series.closes) == 54
    # A pair quote alone, without a history, is no series.
    store_pair_quote(conn, "USDTWD", 32.9, date(2026, 11, 6))
    assert rates_for(conn, "TWD") is None


def test_fetch_rates_reuses_within_the_window_and_forces(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    assert fetch(conn, clients, policy, clock) == RatesOutcome(("SEK",), 1, 0, (), False)
    [stored] = stored_responses(conn)
    assert (stored["provider"], stored["symbol"], stored["http_status"], stored["error"]) == (
        "fmp",
        "USDSEK",
        200,
        None,
    )
    # The pair alone is the reuse key, as the price history's symbol is: the ``from`` date, three
    # years (``refresh.fx_history_years``) before the clock's 2026-11-01, changes daily.
    assert json.loads(stored["params"]) == {"symbol": "USDSEK"}
    assert router.requested[FX_HISTORY] == {"symbol": "USDSEK", "from": "2023-11-01"}
    fixture = FIXTURES / "fmp" / "historical-price-eod-light.USDSEK.json"
    assert stored["payload"] == fixture.read_text(encoding="utf-8")
    assert FMP_KEY not in stored["payload"] and FMP_KEY not in stored["params"]
    assert conn.execute("SELECT count(*) FROM observations").fetchone()[0] == 0  # no rows

    clock.now += timedelta(hours=23)
    assert fetch(conn, clients, policy, clock) == RatesOutcome(("SEK",), 0, 1, (), False)
    assert fetch(conn, clients, policy, clock, force=True) == RatesOutcome(
        ("SEK",), 1, 0, (), False
    )
    clock.now += timedelta(hours=24)  # 24 hours after the forced call
    assert fetch(conn, clients, policy, clock) == RatesOutcome(("SEK",), 1, 0, (), False)
    assert router.calls[FX_HISTORY] == 3 and len(stored_responses(conn)) == 3


def test_fetch_rates_fetches_each_pair_once(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    outcome = fetch(conn, clients, policy, clock, ("SEK", "TWD"))
    assert outcome == RatesOutcome(("SEK", "TWD"), 2, 0, (), False)
    assert [r["symbol"] for r in stored_responses(conn)] == ["USDSEK", "USDTWD"]
    twd = rates_for(conn, "TWD")
    assert twd is not None
    assert twd.at(date(2026, 11, 10), 7) == Rate(32.956, date(2026, 11, 1), NOW, True)


def test_fetch_rates_failure_names_the_currency(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    router.fail = {FX_HISTORY}
    outcome = fetch(conn, clients, policy, clock, ("SEK", "TWD"))
    assert outcome == RatesOutcome((), 2, 0, ("SEK", "TWD"), False)
    assert rates_for(conn, "SEK") is None
    failed = stored_responses(conn)[0]
    assert (failed["symbol"], failed["http_status"], failed["payload"]) == ("USDSEK", 500, None)
    assert "from=2023-11-01" in failed["error"] and FMP_KEY not in failed["error"]

    # An empty list holds no close: unusable, failed and never reused.
    router.fail.clear()
    router.bodies[FX_HISTORY] = b"[]"
    outcome = fetch(conn, clients, policy, clock, ("SEK",))
    assert outcome == RatesOutcome((), 1, 0, ("SEK",), False)
    assert stored_responses(conn)[-1]["error"] == "unusable payload: []"
    assert rates_for(conn, "SEK") is None
    router.bodies.clear()
    assert fetch(conn, clients, policy, clock, ("SEK",)) == RatesOutcome(("SEK",), 1, 0, (), False)


def test_fetch_rates_stops_at_a_429(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    router.fail = {FX_HISTORY}
    router.fail_status = 429
    outcome = fetch(conn, clients, policy, clock, ("SEK", "TWD"))
    assert outcome == RatesOutcome((), 1, 0, ("SEK",), True)
    assert router.symbol_calls["USDTWD"] == 0
    assert [(r["symbol"], r["http_status"]) for r in stored_responses(conn)] == [("USDSEK", 429)]


def test_currencies_of_reads_the_newest_annual_income_statement(
    conn: sqlite3.Connection,
) -> None:
    usd = bodies()["income-annual"]
    store_income(conn, "ACME", usd)
    store_income(conn, "KRON", bodies(currency="SEK")["income-annual"])
    store_income(conn, "SKOG", bodies(currency="SEK")["income-annual"])
    # The newest year names the currency: SEK before, TWD now.
    sek = bodies(currency="SEK")["income-annual"]
    store_income(conn, "TWCO", [*sek[:-1], {**sek[-1], "reportedCurrency": "TWD"}])
    # The newest year names none: no currency, whatever the years before name.
    store_income(conn, "NONE", [*sek[:-1], {**sek[-1], "reportedCurrency": None}])
    # A code that names no pair is no currency.
    store_income(conn, "ODDS", [{**row, "reportedCurrency": "N/A"} for row in usd])
    symbols = ("ACME", "KRON", "SKOG", "TWCO", "NONE", "ODDS", "NOFACTS")
    assert currencies_of(conn, symbols) == ("SEK", "TWD")
    assert currencies_of(conn, ("ACME",)) == ()
    assert currencies_of(conn, ()) == ()
