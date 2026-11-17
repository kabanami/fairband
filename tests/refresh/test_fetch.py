"""``fetch_company`` against the fixture router (never the network) and a migrated temporary
database: what it calls, what it reuses, what it stores, and that no key reaches the store."""

import json
import logging
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import quote, quote_plus

import pytest
from refresh_env import Env
from vendor_double import FIXTURES, FMP_KEY, GF_TOKEN, Clients, Clock, Router

from fairband.policy import Policy
from fairband.refresh import fetch as fetch_module
from fairband.refresh.fetch import FetchOutcome, fetch_company
from fairband.refresh.passthrough import Passthrough
from fairband.store.facts import facts_for
from fairband.store.observations import observations_for
from fairband.store.vendor import response_payload
from fairband.vendors.normalize_fmp import price_closes

# The company page's fourteen, fetched after the two GuruFocus calls: the ten of spec 2026-11-16
# 10.1, then the Financials tab's four of spec 2026-11-17 8.1.
PAGE_ENDPOINTS = (
    "ratios-ttm",
    "key-metrics-ttm",
    "financial-growth",
    "financial-scores",
    "price-change",
    "price-target",
    "grades",
    "dividends",
    "shares-float",
    "news",
    "ratios-annual",
    "key-metrics-annual",
    "segments-product",
    "segments-geographic",
)
# The two segment answers, stored under the pass-through's endpoints and params.
SEGMENTS = ("segments-product", "segments-geographic")
# Each page endpoint's stored fixture, the one every company shares but ACME's own news and
# segments.
PAGE_FIXTURES = {
    "ratios-ttm": "ratios-ttm.json",
    "key-metrics-ttm": "key-metrics-ttm.json",
    "financial-growth": "financial-growth.json",
    "financial-scores": "financial-scores.json",
    "price-change": "stock-price-change.json",
    "price-target": "price-target-consensus.json",
    "grades": "grades-consensus.json",
    "dividends": "dividends.json",
    "shares-float": "shares-float.json",
    "news": "news-stock.ACME.json",
    "ratios-annual": "ratios.annual.json",
    "key-metrics-annual": "key-metrics.annual.json",
    "segments-product": "revenue-product-segmentation.ACME.json",
    "segments-geographic": "revenue-geographic-segmentation.ACME.json",
}
FMP_ENDPOINTS = (
    "income-annual",
    "balance-annual",
    "cashflow-annual",
    "income-quarter",
    "cashflow-quarter",
    "balance-quarter",
    "balance-asreported-annual",
    "profile",
    "quote",
    "price-history",
    "estimates-annual",
    "estimates-quarter",
    "earnings",
    "peers",
    "splits",
    *PAGE_ENDPOINTS,
)
GF_ENDPOINTS = ("summary", "keyratios")
# In fetch order: the fifteen FMP calls the engine reads, GuruFocus's two, the page's fourteen.
ENDPOINTS = (*FMP_ENDPOINTS[: -len(PAGE_ENDPOINTS)], *GF_ENDPOINTS, *PAGE_ENDPOINTS)
# (dataset, the endpoint whose response its rows cite)
DATASETS = {
    ("income-annual", "income-annual"),
    ("balance-annual", "balance-annual"),
    ("cashflow-annual", "cashflow-annual"),
    ("income-quarter", "income-quarter"),
    ("cashflow-quarter", "cashflow-quarter"),
    ("balance-quarter", "balance-quarter"),
    ("balance-asreported-annual", "balance-asreported-annual"),
    ("profile", "profile"),
    ("quote", "quote"),
    ("estimate-annual", "estimates-annual"),
    ("estimate-quarter", "estimates-quarter"),
    ("street-actual", "earnings"),
    ("earnings-date", "earnings"),
    ("gf-score", "summary"),
    ("gf-ratio", "keyratios"),
    ("split", "splits"),
}


def fetch(
    conn: sqlite3.Connection,
    clients: Clients,
    policy: Policy,
    clock: Clock,
    force: bool = False,
) -> FetchOutcome:
    return fetch_company(
        conn, clients.fmp, clients.gf, "ACME", policy, clock(), clients.secrets, force=force
    )


def responses(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    """The newest stored response per endpoint."""
    rows = conn.execute("SELECT * FROM vendor_responses ORDER BY id").fetchall()
    return {row["endpoint"]: row for row in rows}


def count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def stored_datasets(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    """Each stored dataset with the endpoint of the response its rows cite."""
    rows = conn.execute(
        "SELECT DISTINCT d.dataset, r.endpoint FROM ("
        " SELECT dataset, response_id FROM facts"
        " UNION ALL SELECT dataset, response_id FROM observations"
        ") AS d JOIN vendor_responses AS r ON r.id = d.response_id"
    )
    return {(row[0], row[1]) for row in rows}


def test_fetches_all_endpoints_and_stores(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=31, reused=0, failed=(), error=None)
    assert router.calls == Counter(dict.fromkeys(ENDPOINTS, 1))

    stored = responses(conn)
    assert count(conn, "vendor_responses") == 31
    assert [(r["provider"], r["endpoint"]) for r in stored.values()] == [
        ("gf" if e in GF_ENDPOINTS else "fmp", e) for e in ENDPOINTS
    ]
    for row in stored.values():
        assert (row["symbol"], row["http_status"], row["error"]) == ("ACME", 200, None)
        assert row["observed_at"] == clock.now.isoformat()
    income = stored["income-annual"]
    assert json.loads(income["params"]) == {"symbol": "ACME", "period": "annual", "limit": "11"}
    fixture = FIXTURES / "fmp" / "income-statement.annual.ACME.json"
    assert income["payload"] == fixture.read_text(encoding="utf-8")
    # The quarterly balance sheet: eight periods, as the quarterly income statement and cash flow.
    quarterly = {"symbol": "ACME", "period": "quarter", "limit": "8"}
    assert json.loads(stored["balance-quarter"]["params"]) == quarterly
    assert router.requested["balance-quarter"] == quarterly
    assert json.loads(stored["price-history"]["params"]) == {"symbol": "ACME"}
    assert router.requested["price-history"] == {"symbol": "ACME", "from": "2021-11-01"}
    assert json.loads(stored["summary"]["params"]) == {"symbol": "ACME"}
    assert json.loads(stored["peers"]["params"]) == {"symbol": "ACME"}
    assert router.requested["peers"] == {"symbol": "ACME"}
    peers = FIXTURES / "fmp" / "stock-peers.ACME.json"
    assert stored["peers"]["payload"] == peers.read_text(encoding="utf-8")

    assert stored_datasets(conn) == DATASETS
    facts = facts_for(conn, "ACME", "income-annual")
    assert facts and {f.response_id for f in facts} == {income["id"]}
    assert {(f.observed_at, f.entered_at) for f in facts} == {(clock.now, clock.now)}
    [moat] = [o for o in observations_for(conn, "ACME", "gf-score") if o.field == "moat_score"]
    assert moat.value == Decimal(7)
    # The closes stay in the stored payload; nothing is normalized from them here.
    history = response_payload(conn, stored["price-history"]["id"])
    assert history is not None
    assert price_closes(json.loads(history)) == [
        (date(2026, 10, 28), 49.0),
        (date(2026, 10, 29), 49.5),
        (date(2026, 10, 30), 50.0),
    ]
    [adr] = [o for o in observations_for(conn, "ACME", "profile") if o.field == "is_adr"]
    assert adr.value == Decimal(0)


def test_reuses_within_24h(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    fetch(conn, clients, policy, clock)
    # 23 hours on is the next UTC day: the price history's start date moves, its reuse key does not.
    clock.now += timedelta(hours=23)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=0, reused=31, failed=(), error=None)
    assert router.calls.total() == 31
    assert count(conn, "vendor_responses") == 31


def test_force_fetches_fresh_endpoints(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    fetch(conn, clients, policy, clock)
    outcome = fetch(conn, clients, policy, clock, force=True)
    assert outcome == FetchOutcome("ACME", calls=31, reused=0, failed=(), error=None)
    assert router.calls == Counter(dict.fromkeys(ENDPOINTS, 2))
    assert count(conn, "vendor_responses") == 62


def test_gf_reused_for_7_days(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    start = clock.now
    fetch(conn, clients, policy, clock)
    clock.now = start + timedelta(days=2)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=29, reused=2, failed=(), error=None)
    assert router.calls == Counter(
        {**dict.fromkeys(FMP_ENDPOINTS, 2), **dict.fromkeys(GF_ENDPOINTS, 1)}
    )
    # Seven days after the GuruFocus responses were observed they are fetched again.
    clock.now = start + timedelta(days=7)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=31, reused=0, failed=(), error=None)
    assert router.calls["summary"] == router.calls["keyratios"] == 2


def test_response_and_its_rows_commit_together(
    conn: sqlite3.Connection,
    clients: Clients,
    clock: Clock,
    policy: Policy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(conn: sqlite3.Connection, rows: object) -> None:
        raise RuntimeError("disk full")

    # The first endpoint stores its response and facts, then its (empty) observations fail.
    monkeypatch.setattr(fetch_module, "insert_observations", broken)
    with pytest.raises(RuntimeError, match="disk full"):
        fetch(conn, clients, policy, clock)
    assert not conn.in_transaction
    assert (count(conn, "vendor_responses"), count(conn, "facts")) == (0, 0)


def test_refuses_to_run_inside_a_transaction(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    conn.execute("BEGIN")
    with pytest.raises(ValueError, match="fetch_company must not run inside a transaction"):
        fetch(conn, clients, policy, clock)
    conn.rollback()
    assert router.calls.total() == 0


def test_endpoint_failure_recorded_and_continues(
    conn: sqlite3.Connection,
    clients_with_500_on_quote: Clients,
    router: Router,
    clock: Clock,
    policy: Policy,
) -> None:
    clients = clients_with_500_on_quote
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome(
        "ACME", calls=31, reused=0, failed=("quote",), error="data fetch failed: quote"
    )
    assert router.calls["quote"] == policy.refresh.attempts
    failed = responses(conn)["quote"]
    assert (failed["http_status"], failed["payload"]) == (500, None)
    assert failed["error"].startswith(
        "GET https://financialmodelingprep.com/stable/quote?symbol=ACME&apikey=<key> -> 500"
    )
    assert json.loads(failed["params"]) == {"symbol": "ACME"}
    assert failed["observed_at"] == clock.now.isoformat()
    assert stored_datasets(conn) == DATASETS - {("quote", "quote")}

    # A failed call is not reused: the next fetch calls it again and reuses the rest.
    router.fail.clear()
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=1, reused=30, failed=(), error=None)
    assert stored_datasets(conn) == DATASETS


def test_rate_limit_stops_the_company(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    router.fail.add("quote")
    router.fail_status = 429
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome(
        "ACME",
        calls=9,
        reused=0,
        failed=("quote",),
        error="data fetch failed: quote",
        rate_limited=True,
    )
    # The endpoints after the quote were not called.
    before = FMP_ENDPOINTS[: FMP_ENDPOINTS.index("quote")]
    assert router.calls == Counter({**dict.fromkeys(before, 1), "quote": policy.refresh.attempts})
    stored = responses(conn)
    assert list(stored) == [*before, "quote"]
    assert (stored["quote"]["http_status"], stored["quote"]["payload"]) == (429, None)


def test_unusable_200_is_failed_and_not_reused(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    # GuruFocus answers some failures with HTTP 200 and an error body; FMP answers an unknown
    # symbol with an empty list.
    error_body = json.dumps(
        {"error": "Your API token is invalid, or ACME is not covered by your GuruFocus plan."},
        indent=2,
    )
    router.bodies.update({"quote": b"[]", "summary": error_body.encode()})
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome(
        "ACME", calls=31, reused=0, failed=("quote", "summary"), error="data fetch failed: quote"
    )
    stored = responses(conn)
    assert (stored["quote"]["http_status"], stored["quote"]["payload"]) == (200, "[]")
    assert stored["quote"]["error"] == "unusable payload: []"
    summary = stored["summary"]
    assert (summary["http_status"], summary["payload"]) == (200, error_body)
    # Whitespace runs collapse to one space, then the text is cut at 80 characters.
    assert summary["error"] == (
        'unusable payload: { "error": "Your API token is invalid, or ACME is not covered by'
        " your GuruFocus "
    )
    assert stored_datasets(conn) == DATASETS - {("quote", "quote"), ("gf-score", "summary")}

    router.bodies.clear()
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=2, reused=29, failed=(), error=None)
    assert stored_datasets(conn) == DATASETS


def test_only_required_endpoints_set_the_error(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    router.fail.update({"profile", "estimates-quarter", "income-annual", "keyratios"})
    outcome = fetch(conn, clients, policy, clock)
    assert outcome.failed == ("income-annual", "profile", "estimates-quarter", "keyratios")
    assert outcome.error == "data fetch failed: income-annual"
    router.fail = {"profile", "keyratios"}
    outcome = fetch(conn, clients, policy, clock)
    assert (outcome.calls, outcome.failed, outcome.error) == (4, ("profile", "keyratios"), None)


def test_an_empty_quarterly_consensus_is_not_a_fetch_failure(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """FMP answers ``[]`` for a company without quarterly coverage, a foreign filer that reports
    twice a year among them. The endpoint failed, but the company can still be valued or refused
    for its own reason: only the Mature Growth route reads the consensus, and it refuses an
    incomplete one itself."""
    router.bodies["estimates-quarter"] = b"[]"
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome(
        "ACME", calls=31, reused=0, failed=("estimates-quarter",), error=None
    )
    assert responses(conn)["estimates-quarter"]["error"] == "unusable payload: []"


def test_missing_gf_key_marks_gf_failed(
    conn: sqlite3.Connection,
    clients_no_gf: Clients,
    router: Router,
    clock: Clock,
    policy: Policy,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="fairband.refresh")
    outcome = fetch(conn, clients_no_gf, policy, clock)
    assert outcome == FetchOutcome(
        "ACME", calls=29, reused=0, failed=("summary", "keyratios"), error=None
    )
    assert router.calls == Counter(dict.fromkeys(FMP_ENDPOINTS, 1))
    assert set(responses(conn)) == set(FMP_ENDPOINTS)  # no row for a call not made
    assert "ACME gf summary failed: no GuruFocus key" in caplog.text
    assert "ACME gf keyratios failed: no GuruFocus key" in caplog.text


def test_missing_gf_key_still_reuses_fresh_gf_responses(
    conn: sqlite3.Connection,
    clients: Clients,
    clients_no_gf: Clients,
    clock: Clock,
    policy: Policy,
) -> None:
    fetch(conn, clients, policy, clock)
    outcome = fetch(conn, clients_no_gf, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=0, reused=31, failed=(), error=None)
    outcome = fetch(conn, clients_no_gf, policy, clock, force=True)
    assert (outcome.calls, outcome.failed) == (29, ("summary", "keyratios"))


def test_no_key_in_stored_params_or_payload(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    # The failed calls store an error that quotes the request URL, and the profile and key-ratios
    # bodies echo the keys, so the scrub has something to remove in each column.
    router.fail.update({"quote", "summary"})
    echo = [{"symbol": "ACME", "isAdr": False, "note": f"apikey={FMP_KEY} user/{GF_TOKEN}"}]
    router.bodies["profile"] = json.dumps(echo).encode()
    # An unusable answer stores the start of its body as the error.
    router.bodies["keyratios"] = json.dumps({"error": f"invalid token {GF_TOKEN}"}).encode()
    fetch(conn, clients, policy, clock)

    rows = conn.execute("SELECT params, payload, error FROM vendor_responses").fetchall()
    assert len(rows) == 31
    texts = [text for row in rows for text in row if text is not None]
    assert any("<key>" in text for text in texts)
    assert 'unusable payload: {"error": "invalid token <key>"}' in texts
    forms = {
        form for key in clients.secrets for form in (key, quote(key, safe=""), quote_plus(key))
    }
    assert not [text for text in texts for form in forms if form in text]
    assert all("apikey" not in json.loads(row["params"]) for row in rows)
    dump = "\n".join(conn.iterdump())
    assert not [form for form in forms if form in dump]


def test_peers_payload_is_stored_and_not_required(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    router.fail.add("peers")
    outcome = fetch(conn, clients, policy, clock)
    assert outcome.failed == ("peers",) and outcome.error is None
    assert responses(conn)["peers"]["http_status"] == 500


def test_a_peer_list_or_an_empty_list_is_usable_and_nothing_else(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """An object (FMP's error body) and a list of objects without a symbol are unusable and called
    again. A company with no peers has no peers: FMP's ``[]`` is stored and reused. The fixture's
    list, which names peers, is usable (``test_fetches_all_endpoints_and_stores``)."""
    router.bodies["peers"] = b'{"Error Message": "Limit Reach"}'
    outcome = fetch(conn, clients, policy, clock)
    assert (outcome.failed, outcome.error) == (("peers",), None)
    assert responses(conn)["peers"]["error"] == 'unusable payload: {"Error Message": "Limit Reach"}'

    router.bodies["peers"] = b'[{"companyName": "Bolt Industries"}]'
    outcome = fetch(conn, clients, policy, clock)
    assert (outcome.calls, outcome.reused, outcome.failed) == (1, 30, ("peers",))
    assert responses(conn)["peers"]["error"] == (
        'unusable payload: [{"companyName": "Bolt Industries"}]'
    )

    router.bodies["peers"] = b"[]"
    outcome = fetch(conn, clients, policy, clock)
    assert (outcome.calls, outcome.reused, outcome.failed) == (1, 30, ())
    assert (responses(conn)["peers"]["payload"], responses(conn)["peers"]["error"]) == ("[]", None)
    assert fetch(conn, clients, policy, clock).reused == 31
    assert stored_datasets(conn) == DATASETS  # the peers store no rows


def test_splits_are_stored_and_not_required(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """Spec 2026-11-09 10.1: the splits are fetched with the company's datasets and stored as
    observations; an empty list is usable (a company with no split); a failure leaves the
    company valued on what it has."""
    router.bodies["splits"] = b"[]"
    outcome = fetch(conn, clients, policy, clock)
    assert outcome.failed == () and outcome.error is None
    assert responses(conn)["splits"]["error"] is None
    assert observations_for(conn, "ACME", "split") == []
    router.bodies["splits"] = b'{"Error Message": "no"}'
    clock.now += timedelta(days=2)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome.failed == ("splits",) and outcome.error is None
    assert responses(conn)["splits"]["error"] == 'unusable payload: {"Error Message": "no"}'
    router.bodies.pop("splits")
    router.fail.add("splits")
    clock.now += timedelta(days=2)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome.failed == ("splits",) and outcome.error is None
    failed = responses(conn)["splits"]
    assert (failed["http_status"], failed["payload"]) == (500, None)
    assert failed["error"].startswith(
        "GET https://financialmodelingprep.com/stable/splits?symbol=ACME&apikey=<key> -> 500"
    )


def test_the_quarterly_balance_sheet_is_not_required(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """Spec 2026-11-13 12.1: a company whose quarterly balance call answers 404 is fetched with no
    error, so it is valued on its annual sheet (``test_run``); the required endpoints stay the
    three annual statements and the quote."""
    router.fail.add("balance-quarter")
    router.fail_status = 404
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome(
        "ACME", calls=31, reused=0, failed=("balance-quarter",), error=None
    )
    assert fetch_module.REQUIRED == {"income-annual", "balance-annual", "cashflow-annual", "quote"}
    failed = responses(conn)["balance-quarter"]
    assert (failed["http_status"], failed["payload"]) == (404, None)
    assert stored_datasets(conn) == DATASETS - {("balance-quarter", "balance-quarter")}


def test_a_pair_history_stores_no_rows_and_is_usable_with_a_close(clock: Clock) -> None:
    """The rates stage's ``fx-history`` (spec 2026-11-10 7.1) is stored whole, as the price
    history is: no rows, its closes left in the payload, usable when it holds a close. It is
    FMP's."""
    history = json.loads((FIXTURES / "fmp" / "historical-price-eod-light.USDSEK.json").read_text())
    now = clock()
    assert fetch_module._rows("fx-history", history, "USDSEK", now, now) == ([], [])
    no_close = ([], [{"date": "2026-11-05", "price": 0}], {"symbol": "USDSEK"}, None)
    for payload in no_close:
        assert fetch_module._rows("fx-history", payload, "USDSEK", now, now) is None
    assert fetch_module.provider_of("fx-history") == "fmp"


def test_the_page_calls_come_last_in_this_order(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """Spec 2026-11-16 10.1 and spec 2026-11-17 8.1: the company page's fourteen calls follow
    GuruFocus's two, in this order, on their FMP routes, each with its depth: the ratios and the
    key metrics by fiscal year cover the statements' years."""
    assert fetch_module.PAGE_ENDPOINTS == PAGE_ENDPOINTS
    fetch(conn, clients, policy, clock)
    assert list(router.calls) == list(ENDPOINTS)
    assert list(responses(conn))[-15:] == ["keyratios", *PAGE_ENDPOINTS]
    assert router.requested["price-change"] == {"symbol": "ACME"}
    assert router.requested["financial-growth"] == {"symbol": "ACME", "limit": "1"}
    assert router.requested["dividends"] == {"symbol": "ACME", "limit": "4"}
    assert router.requested["news"] == {"symbols": "ACME", "limit": "60"}
    by_year = {"symbol": "ACME", "period": "annual", "limit": "11"}
    assert router.requested["ratios-annual"] == router.requested["key-metrics-annual"] == by_year
    assert router.requested["segments-product"] == {"symbol": "ACME"}
    assert router.requested["segments-geographic"] == {"symbol": "ACME"}
    assert all(fetch_module.provider_of(endpoint) == "fmp" for endpoint in PAGE_ENDPOINTS)


def test_the_page_calls_store_their_params(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """Each stored with the symbol, the period where the call sends one, and the depth as
    ``limit`` where the call sends one; the params have one home, ``page_params``, by which the
    page's reads find the answers."""
    fetch(conn, clients, policy, clock)
    stored = responses(conn)
    by_year = {"symbol": "ACME", "period": "annual", "limit": "11"}
    expected = {endpoint: {"symbol": "ACME"} for endpoint in PAGE_ENDPOINTS} | {
        "financial-growth": {"symbol": "ACME", "limit": "1"},
        "dividends": {"symbol": "ACME", "limit": "4"},
        "news": {"symbol": "ACME", "limit": "60"},
        "ratios-annual": by_year,
        "key-metrics-annual": by_year,
    }
    assert {e: json.loads(stored[e]["params"]) for e in PAGE_ENDPOINTS} == expected
    assert {e: fetch_module.page_params(e, "ACME") for e in PAGE_ENDPOINTS} == expected
    limits = (fetch_module.GROWTH_YEARS, fetch_module.DIVIDEND_ROWS, fetch_module.NEWS_STORIES)
    assert limits == (1, 4, 60)
    for endpoint in ("quote", "summary", "news-stock", "stock-price-change"):
        with pytest.raises(ValueError, match=f"not a page endpoint: {endpoint}"):
            fetch_module.page_params(endpoint, "ACME")
    # Stored whole, as received: ACME's own news and segments, the shared fixture for the rest.
    for endpoint, name in PAGE_FIXTURES.items():
        row = stored[endpoint]
        assert (row["http_status"], row["error"]) == (200, None)
        assert row["payload"] == (FIXTURES / "fmp" / name).read_text(encoding="utf-8")


def test_a_failed_page_call_is_named_and_costs_nothing(
    conn: sqlite3.Connection,
    clients: Clients,
    router: Router,
    clock: Clock,
    policy: Policy,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """None of the fourteen is required: each failure is logged and named, and the error stays
    ``None``, so the company is valued (``test_run``)."""
    caplog.set_level(logging.WARNING, logger="fairband.refresh")
    router.fail = set(PAGE_ENDPOINTS)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=31, reused=0, failed=PAGE_ENDPOINTS, error=None)
    assert all(f"ACME fmp {e} failed: GET " in caplog.text for e in PAGE_ENDPOINTS)
    stored = responses(conn)
    assert {(stored[e]["http_status"], stored[e]["payload"]) for e in PAGE_ENDPOINTS} == {
        (500, None)
    }
    assert stored_datasets(conn) == DATASETS


def test_a_page_payload_is_usable_when_it_is_a_list(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """An object (FMP's error body) is unusable: stored with its error and called again. A list is
    usable, the empty list among them (a company with no dividend, no analyst, no news or no
    segments), and reused like any other answer."""
    router.bodies.update(dict.fromkeys(PAGE_ENDPOINTS, b'{"Error Message": "x"}'))
    outcome = fetch(conn, clients, policy, clock)
    assert (outcome.calls, outcome.failed, outcome.error) == (31, PAGE_ENDPOINTS, None)
    stored = responses(conn)
    for endpoint in PAGE_ENDPOINTS:
        row = stored[endpoint]
        assert (row["http_status"], row["payload"]) == (200, '{"Error Message": "x"}')
        assert row["error"] == 'unusable payload: {"Error Message": "x"}'
    outcome = fetch(conn, clients, policy, clock)
    assert (outcome.calls, outcome.reused, outcome.failed) == (14, 17, PAGE_ENDPOINTS)

    router.bodies.update(dict.fromkeys(PAGE_ENDPOINTS, b"[]"))
    outcome = fetch(conn, clients, policy, clock)
    assert (outcome.calls, outcome.reused, outcome.failed) == (14, 17, ())
    stored = responses(conn)
    assert {(stored[e]["payload"], stored[e]["error"]) for e in PAGE_ENDPOINTS} == {("[]", None)}
    calls = router.calls.total()
    assert fetch(conn, clients, policy, clock) == FetchOutcome(
        "ACME", calls=0, reused=31, failed=(), error=None
    )
    assert router.calls.total() == calls


def test_a_page_call_gives_no_fact_and_no_observation(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """The page reads the stored payloads; nothing is normalized from them."""
    fetch(conn, clients, policy, clock)
    stored = responses(conn)
    page_ids = [stored[endpoint]["id"] for endpoint in PAGE_ENDPOINTS]
    marks = ", ".join("?" * len(page_ids))
    for table in ("facts", "observations"):
        cited = f"SELECT count(*) FROM {table} WHERE response_id IN ({marks})"
        assert conn.execute(cited, page_ids).fetchone()[0] == 0
    assert stored_datasets(conn) == DATASETS
    now = clock()
    for endpoint, name in PAGE_FIXTURES.items():
        payload = json.loads((FIXTURES / "fmp" / name).read_text())
        assert payload and fetch_module._rows(endpoint, payload, "ACME", now, now) == ([], [])
        assert fetch_module._rows(endpoint, [], "ACME", now, now) == ([], [])
        for unusable in ({"Error Message": "x"}, None, "167000"):
            assert fetch_module._rows(endpoint, unusable, "ACME", now, now) is None


def test_a_429_on_a_page_call_stops_the_fetch(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """As on any call: the fetch stops there and reports ``rate_limited``, and the runner stops
    the refresh. The page calls after it are not called; the error stays ``None``."""
    router.fail.add("grades")
    router.fail_status = 429
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome(
        "ACME", calls=24, reused=0, failed=("grades",), error=None, rate_limited=True
    )
    assert router.calls["grades"] == policy.refresh.attempts
    after = PAGE_ENDPOINTS[PAGE_ENDPOINTS.index("grades") + 1 :]
    assert after == (
        "dividends",
        "shares-float",
        "news",
        "ratios-annual",
        "key-metrics-annual",
        *SEGMENTS,
    )
    assert not [endpoint for endpoint in after if router.calls[endpoint]]
    stored = responses(conn)
    assert list(stored)[-1] == "grades"
    assert (stored["grades"]["http_status"], stored["grades"]["payload"]) == (429, None)


def env_passthrough(env: Env) -> Passthrough:
    """The pass-through over the environment's clients and database."""
    clients = env.clients
    return Passthrough(clients.fmp, env.connect, env.policy, env.clock, clients.secrets, clients.gf)


def env_fetch(env: Env, symbol: str) -> FetchOutcome:
    """``fetch_company`` for ``symbol`` on the environment's clients and database."""
    clients = env.clients
    with closing(env.connect()) as conn:
        return fetch_company(
            conn, clients.fmp, clients.gf, symbol, env.policy, env.clock(), clients.secrets
        )


def test_the_news_is_stored_under_the_pass_through_s_key(env: Env) -> None:
    """Spec 2026-11-16 10.1: the refresh's news and the pass-through's at the same limit, 60, are
    one reuse key, so each reuses the other's copy."""
    passthrough = env_passthrough(env)
    assert env_fetch(env, "ACME").failed == ()
    assert env.router.calls["news"] == 1
    fetched = passthrough.fetch("news", "ACME", {"limit": "60"})["news"]
    assert fetched.reused and env.router.calls["news"] == 1
    assert fetched.payload == json.loads((FIXTURES / "fmp" / "news-stock.ACME.json").read_text())

    # The other way round: BOLT's news, fetched by the pass-through first, the fetch reuses.
    fresh = passthrough.fetch("news", "BOLT", {"limit": "60"})["news"]
    assert not fresh.reused and env.router.calls["news"] == 2
    outcome = env_fetch(env, "BOLT")
    assert (outcome.failed, outcome.reused) == ((), 1)
    assert env.router.calls["news"] == 2


def test_a_news_error_body_the_pass_through_stored_is_not_reused(env: Env) -> None:
    """FMP answers some failures with HTTP 200 and ``{"Error Message": ...}``. The pass-through
    stores such a news answer with its error and answers it as fetched, so neither it nor the
    fetch, which shares its key at 60, reuses it: the fetch calls the news again."""
    env.router.bodies["news"] = b'{"Error Message": "x"}'
    passthrough = env_passthrough(env)
    first = passthrough.fetch("news", "ACME", {"limit": "60"})["news"]
    assert (first.reused, first.payload) == (False, {"Error Message": "x"})
    assert first.row.error == 'unusable payload: {"Error Message": "x"}'
    assert passthrough.fetch("news", "ACME", {"limit": "60"})["news"].reused is False
    assert env.router.calls["news"] == 2

    del env.router.bodies["news"]
    outcome = env_fetch(env, "ACME")
    assert (outcome.failed, outcome.reused) == ((), 0)
    assert env.router.calls["news"] == 3


def segment_calls(env: Env) -> tuple[int, int]:
    """The calls made so far to the two segment routes, the product's then the region's."""
    return env.router.calls["segments-product"], env.router.calls["segments-geographic"]


def test_the_segments_are_stored_under_the_pass_through_s_key(env: Env) -> None:
    """Spec 2026-11-17 8.1: the refresh's two segment answers and the pass-through's are one reuse
    key each, the symbol alone, so each reuses the other's copy."""
    passthrough = env_passthrough(env)
    assert env_fetch(env, "ACME").failed == ()
    assert segment_calls(env) == (1, 1)
    parts = passthrough.fetch("segments", "ACME", {})
    assert [part.reused for part in parts.values()] == [True, True]
    assert segment_calls(env) == (1, 1)
    for part in ("product", "geographic"):
        fixture = FIXTURES / "fmp" / f"revenue-{part}-segmentation.ACME.json"
        assert parts[part].payload == json.loads(fixture.read_text())

    # The other way round: BOLT's segments, fetched by the pass-through first, the fetch reuses.
    fresh = passthrough.fetch("segments", "BOLT", {})
    assert [part.reused for part in fresh.values()] == [False, False]
    assert segment_calls(env) == (2, 2)
    outcome = env_fetch(env, "BOLT")
    assert (outcome.failed, outcome.reused) == ((), 2)
    assert segment_calls(env) == (2, 2)


def test_a_segments_error_body_the_pass_through_stored_is_not_reused(env: Env) -> None:
    """FMP answers some failures with HTTP 200 and ``{"Error Message": ...}``; a pass-through
    built before the refresh fetched the segments may have stored one. The pass-through stores
    such an answer with its error, so the fetch, which shares its key, does not reuse it: it calls
    both routes again."""
    env.router.bodies.update(dict.fromkeys(SEGMENTS, b'{"Error Message": "x"}'))
    parts = env_passthrough(env).fetch("segments", "ACME", {})
    for part in parts.values():
        assert (part.reused, part.payload) == (False, {"Error Message": "x"})
        assert part.row.error is not None and part.row.error.startswith("unusable payload:")
    assert segment_calls(env) == (1, 1)

    for endpoint in SEGMENTS:
        del env.router.bodies[endpoint]
    outcome = env_fetch(env, "ACME")
    assert (outcome.failed, outcome.reused) == ((), 0)
    assert segment_calls(env) == (2, 2)
