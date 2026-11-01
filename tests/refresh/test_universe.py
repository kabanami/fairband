"""``build_universe`` against the fixture router (never the network) and a migrated temporary
database: which screener rows are admitted, recorded as excluded or skipped, and the reuse."""

import json
import sqlite3
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from vendor_double import FMP_KEY, Clients, Clock, Router

from fairband.policy import Policy
from fairband.refresh.universe import UniverseResult, build_universe
from fairband.store.companies import CompanyRow, latest_companies
from fairband.store.refreshes import create_refresh, finish_refresh
from fairband.store.vendor import latest_response
from fairband.vendors.http import VendorError

B = 1_000_000_000


def build(
    conn: sqlite3.Connection, clients: Clients, policy: Policy, clock: Clock
) -> UniverseResult:
    """The universe of a new full refresh, which is then closed so the next one may start."""
    refresh_id = create_refresh(conn, "full", None, policy.version, "m", clock())
    result = build_universe(conn, clients.fmp, policy, refresh_id, clock(), clients.secrets)
    finish_refresh(conn, refresh_id, "done", clock())
    return result


def stored(conn: sqlite3.Connection) -> dict[str, CompanyRow]:
    """The latest universe's rows, the excluded ones among them, by symbol."""
    return {c.symbol: c for c in latest_companies(conn, eligible_only=False)}


def listing(symbol: str, market_cap: float = 5 * B, **fields: Any) -> dict[str, Any]:
    """A screener row for an admissible NYSE common stock, with ``fields`` changed."""
    return {
        "symbol": symbol,
        "companyName": f"{symbol} Inc",
        "marketCap": market_cap,
        "sector": "Industrials",
        "industry": "Conglomerates",
        "exchangeShortName": "NYSE",
        "country": "US",
        "isEtf": False,
        "isFund": False,
        "isActivelyTrading": True,
        **fields,
    }


def serve(router: Router, *rows: dict[str, Any]) -> None:
    router.bodies["screener"] = json.dumps(list(rows)).encode()


def screener_responses(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM vendor_responses WHERE endpoint = 'screener' ORDER BY id"
    ).fetchall()


def test_admits_and_excludes_each_fixture_case(
    conn: sqlite3.Connection, clients: Clients, policy: Policy, clock: Clock
) -> None:
    result = build(conn, clients, policy, clock)
    # One common stock on each exchange, the BRK-B share class in the exchange form, the ADR.
    assert result.admitted == ("ACME", "BOLT", "BRK.B", "CAPE", "ADRX")
    # The OTC listing, the listing below the floor, the ETF and the second ACME are skipped.
    assert result.excluded == {
        "industry": 2,
        "symbol pattern": 3,
        "manual exclusion": 0,
        "skipped": 4,
    }
    rows = stored(conn)
    assert {symbol: (row.eligible, row.exclusion_reason) for symbol, row in rows.items()} == {
        "ACME": (True, None),
        "ACME-PA": (False, "symbol pattern"),
        "ADRX": (True, None),
        "BOLT": (True, None),
        "BOLT-WS": (False, "symbol pattern"),
        "BRK.B": (True, None),
        "CAPE": (True, None),
        "FIRB": (False, "industry: Banks - Regional"),
        "NEWC.U": (False, "symbol pattern"),
        "OFFR": (False, "industry: REIT - Office"),
    }
    assert rows["ACME"] == CompanyRow(
        symbol="ACME",
        refresh_id=result.refresh_id,
        name="Acme Corp",
        exchange="NASDAQ",
        sector="Industrials",
        industry="Specialty Industrial Machinery",
        country="US",
        currency=None,
        is_adr=False,
        cap_band="Mid",
        market_cap=Decimal(5 * B),
        eligible=True,
        exclusion_reason=None,
        observed_at=clock.now,
    )
    # The screener's isAdr is ignored: the profile decides it (Task 18), as the statements decide
    # the currency.
    adr = rows["ADRX"]
    assert (adr.is_adr, adr.currency, adr.country) == (False, None, "GB")
    assert rows["FIRB"].cap_band is None and rows["FIRB"].market_cap == Decimal(4 * B)


def test_cap_bands(
    conn: sqlite3.Connection, clients: Clients, router: Router, policy: Policy, clock: Clock
) -> None:
    serve(
        router,
        listing("BELOW", 2 * B - 1),
        listing("FLOOR", 2 * B),
        listing("MID", 10 * B - 1),
        listing("LARGE", 10 * B),
        listing("HIGH", 200 * B - 1),
        listing("MEGA", 200 * B),
    )
    result = build(conn, clients, policy, clock)
    assert result.admitted == ("FLOOR", "MID", "LARGE", "HIGH", "MEGA")
    assert result.excluded["skipped"] == 1
    assert {symbol: row.cap_band for symbol, row in stored(conn).items()} == {
        "FLOOR": "Mid",
        "MID": "Mid",
        "LARGE": "Large",
        "HIGH": "Large",
        "MEGA": "Mega",
    }


def test_duplicate_symbol_kept_once(
    conn: sqlite3.Connection, clients: Clients, router: Router, policy: Policy, clock: Clock
) -> None:
    result = build(conn, clients, policy, clock)
    assert result.admitted.count("ACME") == 1
    acme = stored(conn)["ACME"]  # the first row: on NASDAQ at $5 bn, not on NYSE at $6 bn
    assert (acme.exchange, acme.market_cap) == ("NASDAQ", Decimal(5 * B))
    # A first row that is skipped leaves the symbol to the next row that is recorded.
    serve(router, listing("DUPE", exchangeShortName="OTC"), listing("DUPE"), listing("DUPE"))
    clock.now += timedelta(hours=policy.refresh.reuse_hours)  # past the reuse window
    result = build(conn, clients, policy, clock)
    assert result.admitted == ("DUPE",) and result.excluded["skipped"] == 2
    assert stored(conn)["DUPE"].exchange == "NYSE"


def test_screener_reused_within_24h(
    conn: sqlite3.Connection, clients: Clients, router: Router, policy: Policy, clock: Clock
) -> None:
    first = build(conn, clients, policy, clock)
    observed = clock.now
    clock.now += timedelta(hours=23)
    second = build(conn, clients, policy, clock)
    assert router.calls["screener"] == 1
    assert second.refresh_id != first.refresh_id
    assert (second.admitted, second.excluded) == (first.admitted, first.excluded)
    rows = stored(conn)  # the second refresh's rows, observed when the reused response was
    assert {row.refresh_id for row in rows.values()} == {second.refresh_id}
    assert {row.observed_at for row in rows.values()} == {observed}
    clock.now += timedelta(hours=2)
    build(conn, clients, policy, clock)
    assert router.calls["screener"] == 2
    assert router.requested["screener"]["exchange"] == "NYSE,NASDAQ,AMEX"
    calls = [(r["provider"], r["params"], r["symbol"]) for r in screener_responses(conn)]
    assert calls == [("fmp", "{}", None)] * 2


def test_stored_screener_response_is_scrubbed(
    conn: sqlite3.Connection, clients: Clients, router: Router, policy: Policy, clock: Clock
) -> None:
    serve(router, listing("ACME", companyName=f"Acme {FMP_KEY}"))
    build(conn, clients, policy, clock)
    [response] = screener_responses(conn)
    assert FMP_KEY not in response["payload"] and "<key>" in response["payload"]


@pytest.mark.parametrize(
    "industry",
    ["Banks", "banks - regional", "BANKS - DIVERSIFIED", "REIT - Data Center", "Insurance - Title"],
)
def test_industry_excluded_case_insensitively_by_its_first_word_group(
    conn: sqlite3.Connection,
    clients: Clients,
    router: Router,
    policy: Policy,
    clock: Clock,
    industry: str,
) -> None:
    serve(router, listing("ACME", industry=industry))
    result = build(conn, clients, policy, clock)
    assert result.admitted == () and result.excluded["industry"] == 1
    assert stored(conn)["ACME"].exclusion_reason == f"industry: {industry}"


@pytest.mark.parametrize("industry", ["Real Estate Services", "Asset Management", None])
def test_industry_outside_the_list_is_admitted(
    conn: sqlite3.Connection,
    clients: Clients,
    router: Router,
    policy: Policy,
    clock: Clock,
    industry: str | None,
) -> None:
    serve(router, listing("ACME", industry=industry))
    assert build(conn, clients, policy, clock).admitted == ("ACME",)


def test_exchange_compared_case_insensitively(
    conn: sqlite3.Connection, clients: Clients, router: Router, policy: Policy, clock: Clock
) -> None:
    serve(
        router,
        listing("NASD", exchangeShortName="Nasdaq"),
        listing("LOWER", exchangeShortName="nyse"),
        listing("ARCA", exchangeShortName="NYSE Arca"),
        listing("NONE", exchangeShortName=None),
    )
    result = build(conn, clients, policy, clock)
    assert result.admitted == ("NASD", "LOWER") and result.excluded["skipped"] == 2
    assert stored(conn)["NASD"].exchange == "Nasdaq"


def test_funds_and_inactive_listings_are_skipped(
    conn: sqlite3.Connection, clients: Clients, router: Router, policy: Policy, clock: Clock
) -> None:
    serve(
        router,
        listing("FUND", isFund=True),
        listing("GONE", isActivelyTrading=False),
        listing("NOCAP", marketCap=None),
        listing("ACME"),
    )
    result = build(conn, clients, policy, clock)
    assert result.admitted == ("ACME",) and result.excluded["skipped"] == 3
    assert set(stored(conn)) == {"ACME"}


def test_manual_exclusion(
    conn: sqlite3.Connection, clients: Clients, policy: Policy, clock: Clock
) -> None:
    excluding = replace(policy, universe=replace(policy.universe, manual_exclusions=("BOLT",)))
    result = build(conn, clients, excluding, clock)
    assert "BOLT" not in result.admitted and result.excluded["manual exclusion"] == 1
    assert stored(conn)["BOLT"].exclusion_reason == "manual exclusion"


def test_screener_failure_propagates(
    conn: sqlite3.Connection, clients: Clients, router: Router, policy: Policy, clock: Clock
) -> None:
    router.fail.add("screener")
    router.fail_status = 403
    with pytest.raises(VendorError):
        build(conn, clients, policy, clock)
    [response] = screener_responses(conn)
    assert response["http_status"] == 403 and response["error"] and response["payload"] is None
    assert stored(conn) == {}


@pytest.mark.parametrize(
    "body", [b"[]", b'{"Error Message": "Limit Reach"}', b'[{"companyName": "no symbol"}]']
)
def test_unusable_screener_payload(
    conn: sqlite3.Connection,
    clients: Clients,
    router: Router,
    policy: Policy,
    clock: Clock,
    body: bytes,
) -> None:
    router.bodies["screener"] = body
    with pytest.raises(ValueError, match="screener returned no rows"):
        build(conn, clients, policy, clock)
    [response] = screener_responses(conn)
    assert response["error"].startswith("unusable payload")
    assert latest_response(conn, "fmp", "screener", None, {}) is None  # never reused
    assert stored(conn) == {}


def test_refuses_to_run_inside_a_transaction(
    conn: sqlite3.Connection, clients: Clients, router: Router, policy: Policy, clock: Clock
) -> None:
    refresh_id = create_refresh(conn, "full", None, policy.version, "m", clock())
    conn.execute("BEGIN")
    with pytest.raises(ValueError, match="transaction"):
        build_universe(conn, clients.fmp, policy, refresh_id, clock(), clients.secrets)
    conn.rollback()
    assert router.calls["screener"] == 0
