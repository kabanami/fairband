"""``fetch_company`` against the fixture router (never the network) and a migrated temporary
database: what it calls, what it reuses, what it stores, and that no key reaches the store."""

import json
import logging
import sqlite3
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import quote, quote_plus

import pytest
from vendor_double import FIXTURES, FMP_KEY, GF_TOKEN, Clients, Clock, Router

from fairband.policy import Policy
from fairband.refresh import fetch as fetch_module
from fairband.refresh.fetch import FetchOutcome, fetch_company
from fairband.store.facts import facts_for
from fairband.store.observations import observations_for
from fairband.store.vendor import response_payload
from fairband.vendors.normalize_fmp import price_closes

FMP_ENDPOINTS = (
    "income-annual",
    "balance-annual",
    "cashflow-annual",
    "income-quarter",
    "cashflow-quarter",
    "balance-asreported-annual",
    "profile",
    "quote",
    "price-history",
    "estimates-annual",
    "estimates-quarter",
    "earnings",
    "peers",
    "splits",
)
GF_ENDPOINTS = ("summary", "keyratios")
ENDPOINTS = FMP_ENDPOINTS + GF_ENDPOINTS
# (dataset, the endpoint whose response its rows cite)
DATASETS = {
    ("income-annual", "income-annual"),
    ("balance-annual", "balance-annual"),
    ("cashflow-annual", "cashflow-annual"),
    ("income-quarter", "income-quarter"),
    ("cashflow-quarter", "cashflow-quarter"),
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
    assert outcome == FetchOutcome("ACME", calls=16, reused=0, failed=(), error=None)
    assert router.calls == Counter(dict.fromkeys(ENDPOINTS, 1))

    stored = responses(conn)
    assert count(conn, "vendor_responses") == 16
    assert [(r["provider"], r["endpoint"]) for r in stored.values()] == [
        *(("fmp", e) for e in FMP_ENDPOINTS),
        *(("gf", e) for e in GF_ENDPOINTS),
    ]
    for row in stored.values():
        assert (row["symbol"], row["http_status"], row["error"]) == ("ACME", 200, None)
        assert row["observed_at"] == clock.now.isoformat()
    income = stored["income-annual"]
    assert json.loads(income["params"]) == {"symbol": "ACME", "period": "annual", "limit": "11"}
    fixture = FIXTURES / "fmp" / "income-statement.annual.ACME.json"
    assert income["payload"] == fixture.read_text(encoding="utf-8")
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
    assert outcome == FetchOutcome("ACME", calls=0, reused=16, failed=(), error=None)
    assert router.calls.total() == 16
    assert count(conn, "vendor_responses") == 16


def test_force_fetches_fresh_endpoints(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    fetch(conn, clients, policy, clock)
    outcome = fetch(conn, clients, policy, clock, force=True)
    assert outcome == FetchOutcome("ACME", calls=16, reused=0, failed=(), error=None)
    assert router.calls == Counter(dict.fromkeys(ENDPOINTS, 2))
    assert count(conn, "vendor_responses") == 32


def test_gf_reused_for_7_days(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    start = clock.now
    fetch(conn, clients, policy, clock)
    clock.now = start + timedelta(days=2)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=14, reused=2, failed=(), error=None)
    assert router.calls == Counter(
        {**dict.fromkeys(FMP_ENDPOINTS, 2), **dict.fromkeys(GF_ENDPOINTS, 1)}
    )
    # Seven days after the GuruFocus responses were observed they are fetched again.
    clock.now = start + timedelta(days=7)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome("ACME", calls=16, reused=0, failed=(), error=None)
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
        "ACME", calls=16, reused=0, failed=("quote",), error="data fetch failed: quote"
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
    assert outcome == FetchOutcome("ACME", calls=1, reused=15, failed=(), error=None)
    assert stored_datasets(conn) == DATASETS


def test_rate_limit_stops_the_company(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    router.fail.add("quote")
    router.fail_status = 429
    outcome = fetch(conn, clients, policy, clock)
    assert outcome == FetchOutcome(
        "ACME",
        calls=8,
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
        "ACME", calls=16, reused=0, failed=("quote", "summary"), error="data fetch failed: quote"
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
    assert outcome == FetchOutcome("ACME", calls=2, reused=14, failed=(), error=None)
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
        "ACME", calls=16, reused=0, failed=("estimates-quarter",), error=None
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
        "ACME", calls=14, reused=0, failed=("summary", "keyratios"), error=None
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
    assert outcome == FetchOutcome("ACME", calls=0, reused=16, failed=(), error=None)
    outcome = fetch(conn, clients_no_gf, policy, clock, force=True)
    assert (outcome.calls, outcome.failed) == (14, ("summary", "keyratios"))


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
    assert len(rows) == 16
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
    assert (outcome.calls, outcome.reused, outcome.failed) == (1, 15, ("peers",))
    assert responses(conn)["peers"]["error"] == (
        'unusable payload: [{"companyName": "Bolt Industries"}]'
    )

    router.bodies["peers"] = b"[]"
    outcome = fetch(conn, clients, policy, clock)
    assert (outcome.calls, outcome.reused, outcome.failed) == (1, 15, ())
    assert (responses(conn)["peers"]["payload"], responses(conn)["peers"]["error"]) == ("[]", None)
    assert fetch(conn, clients, policy, clock).reused == 16
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
