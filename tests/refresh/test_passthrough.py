"""The vendor pass-throughs on the fixture router: each kind's call, stored scrubbed and reused
inside ``reuse_hours``, the one limiter the worker's client and the pass-through's share, and the
slots that bound the vendor calls in flight."""

import json
import threading
from contextlib import closing
from datetime import timedelta
from typing import Any

import httpx
import pytest
from refresh_env import Env
from vendor_double import FIXTURES, FMP_KEY, GF_TOKEN

from fairband.config import Keys
from fairband.refresh.clients import build_clients, build_fmp
from fairband.refresh.fetch import fetch_company
from fairband.refresh.passthrough import KINDS, PASSTHROUGH_SLOTS, Passthrough
from fairband.reports.refs import Resolved, resolve
from fairband.store.vendor import response_payload, response_row
from fairband.vendors import fmp as fmp_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorError, VendorHttp
from fairband.vendors.limiter import PaceTotals, RateLimiter

Q3 = {"year": "2026", "quarter": "3"}


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / "fmp" / name).read_text())


def _passthrough(env: Env) -> Passthrough:
    return Passthrough(env.clients.fmp, env.connect, env.policy, env.clock, env.clients.secrets)


def _stored(env: Env, response_id: int) -> tuple[str, str | None, dict[str, str], str | None]:
    """The stored row's endpoint, symbol, params and error."""
    with closing(env.connect()) as conn:
        row = response_row(conn, response_id)
    assert row is not None
    return row.endpoint, row.symbol, row.params, row.error


def test_kinds() -> None:
    assert KINDS == ("transcript", "news", "segments", "insider-trades")


def test_a_transcript_is_fetched_stored_and_reused(env: Env) -> None:
    passthrough = _passthrough(env)
    [(part, first)] = passthrough.fetch("transcript", "ACME", Q3).items()
    second = passthrough.fetch("transcript", "ACME", Q3)["transcript"]
    assert part == "transcript"
    assert env.router.calls == {"transcript": 1}
    assert env.router.requested["transcript"] == {"symbol": "ACME", "year": "2026", "quarter": "3"}
    assert (first.reused, second.reused) == (False, True)
    assert first.row == second.row and first.row.observed_at == env.clock()
    assert first.payload == second.payload == _fixture("earning-call-transcript.ACME.json")
    params = {"symbol": "ACME", "year": "2026", "quarter": "3"}
    assert _stored(env, first.row.id) == ("transcript", "ACME", params, None)
    assert first.row.provider == "fmp" and first.row.http_status == 200
    # Another quarter is another call; past the reuse window the same one is called again.
    other = passthrough.fetch("transcript", "ACME", {"year": "2026", "quarter": "2"})
    assert other["transcript"].reused is False
    env.clock.now += timedelta(hours=env.policy.refresh.reuse_hours)
    third = passthrough.fetch("transcript", "ACME", Q3)["transcript"]
    assert third.reused is False and third.row.id > other["transcript"].row.id
    assert env.router.calls == {"transcript": 3}


def test_segments_fetch_two_endpoints(env: Env) -> None:
    passthrough = _passthrough(env)
    parts = passthrough.fetch("segments", "ACME", {})
    assert list(parts) == ["product", "geographic"]
    product, geographic = parts["product"], parts["geographic"]
    assert env.router.calls == {"segments-product": 1, "segments-geographic": 1}
    assert product.payload == _fixture("revenue-product-segmentation.ACME.json")
    assert geographic.payload == _fixture("revenue-geographic-segmentation.ACME.json")
    assert _stored(env, product.row.id) == ("segments-product", "ACME", {"symbol": "ACME"}, None)
    assert _stored(env, geographic.row.id)[0] == "segments-geographic"
    again = passthrough.fetch("segments", "ACME", {})
    assert [f.reused for f in again.values()] == [True, True]
    assert env.router.calls == {"segments-product": 1, "segments-geographic": 1}


def test_a_fetched_response_is_citable(env: Env) -> None:
    product = _passthrough(env).fetch("segments", "ACME", {})["product"]
    ref = f"response:{product.row.id}/0/data/Widgets"
    with closing(env.connect()) as conn:
        assert resolve(conn, "ACME", ref, env.policy) == Resolved(2900000000, None, None, None)
        assert resolve(conn, "BOLT", ref, env.policy) is None  # another company's response


@pytest.mark.parametrize(
    ("kind", "params", "endpoint", "stored", "requested", "fixture"),
    [
        pytest.param(
            "news",
            {},
            "news",
            {"symbol": "ACME", "limit": "20"},
            {"symbols": "ACME", "limit": "20"},
            "news-stock.ACME.json",
            id="news-default-limit",
        ),
        pytest.param(
            "news",
            {"limit": "5"},
            "news",
            {"symbol": "ACME", "limit": "5"},
            {"symbols": "ACME", "limit": "5"},
            "news-stock.ACME.json",
            id="news-limit",
        ),
        pytest.param(
            "insider-trades",
            {},
            "insider-trades",
            {"symbol": "ACME", "limit": "100"},  # the page size is in the reuse key
            {"symbol": "ACME", "page": "0", "limit": "100"},
            "insider-trading-search.ACME.json",
            id="insider-trades",
        ),
    ],
)
def test_each_kind_stores_its_call(
    env: Env,
    kind: str,
    params: dict[str, str],
    endpoint: str,
    stored: dict[str, str],
    requested: dict[str, str],
    fixture: str,
) -> None:
    [fetched] = _passthrough(env).fetch(kind, "ACME", params).values()
    assert env.router.requested[endpoint] == requested
    assert _stored(env, fetched.row.id) == (endpoint, "ACME", stored, None)
    assert fetched.payload == _fixture(fixture)


def test_the_stored_payload_and_the_answer_carry_no_key(env: Env) -> None:
    """A vendor that echoed a key in its body: the store and the answer hold ``<key>``."""
    echoed = [{"title": f"see https://example.com/?apikey={FMP_KEY}&token={GF_TOKEN}"}]
    env.router.bodies["news"] = json.dumps(echoed).encode()
    fetched = _passthrough(env).fetch("news", "ACME", {})["news"]
    with closing(env.connect()) as conn:
        payload = response_payload(conn, fetched.row.id)
    assert payload is not None and FMP_KEY not in payload and GF_TOKEN not in payload
    assert fetched.payload == [{"title": "see https://example.com/?apikey=<key>&token=<key>"}]


def test_a_vendor_error_is_stored_and_raised_scrubbed(env: Env) -> None:
    env.router.fail.add("transcript")
    env.router.fail_status = 403
    passthrough = _passthrough(env)
    with pytest.raises(VendorError) as caught:
        passthrough.fetch("transcript", "ACME", Q3)
    message = str(caught.value)
    assert caught.value.status == 403 and FMP_KEY not in message and "apikey=<key>" in message
    with closing(env.connect()) as conn:
        rows = conn.execute("SELECT endpoint, http_status, payload, error FROM vendor_responses")
        assert [tuple(r) for r in rows] == [("transcript", 403, None, message)]
    env.router.fail.clear()
    assert passthrough.fetch("transcript", "ACME", Q3)["transcript"].reused is False


@pytest.mark.parametrize(
    ("kind", "params", "message"),
    [
        ("filings", {}, "unknown vendor kind: filings"),
        ("transcript", {"year": "2026"}, "a transcript needs year and quarter"),
        ("transcript", {"quarter": "3"}, "a transcript needs year and quarter"),
        ("transcript", {"year": "2026", "quarter": "5"}, "quarter must be 1 to 4"),
        ("transcript", {"year": "last", "quarter": "3"}, "year must be a whole number"),
        ("news", {"limit": "0"}, "limit is 1 to 100"),
        ("news", {"limit": "101"}, "limit is 1 to 100"),
    ],
)
def test_a_bad_request_is_a_value_error_before_any_call(
    env: Env, kind: str, params: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _passthrough(env).fetch(kind, "ACME", params)
    assert env.router.calls == {}


def test_a_shared_limiter_paces_both_clients(env: Env) -> None:
    """The worker's client and the pass-through's take their slots from one ``RateLimiter``:
    ``totals()`` counts both, and the pass-through's call waits behind the worker's."""
    sleeps: list[float] = []
    pace = env.policy.refresh.fmp_calls_per_minute
    limiter = RateLimiter(pace, env.clock, sleeps.append)
    keys = Keys(FMP_KEY, None)
    transport = env.router.transport
    worker_fmp, _, secrets = build_clients(keys, env.policy, transport=transport, limiter=limiter)
    passthrough_fmp = build_fmp(keys, env.policy, transport=transport, limiter=limiter)
    try:
        assert worker_fmp.limiter is passthrough_fmp.limiter is limiter
        with closing(env.connect()) as conn:
            outcome = fetch_company(
                conn, worker_fmp, None, "ACME", env.policy, env.clock(), secrets
            )
        passthrough = Passthrough(passthrough_fmp, env.connect, env.policy, env.clock, secrets)
        fetched = passthrough.fetch("transcript", "ACME", Q3)["transcript"]
    finally:
        worker_fmp.close()
        passthrough_fmp.close()
    assert fetched.reused is False and outcome.calls == 13
    # The clock stands still, so the n-th call waits n slots: 0 + 1 + ... + 13.
    interval = limiter.interval.total_seconds()  # 60 / pace, to the microsecond
    assert limiter.totals() == PaceTotals(14, pytest.approx(91 * interval), 0)
    assert sleeps[-1] == pytest.approx(13 * interval)


def test_a_fifth_vendor_call_waits_for_a_slot(env: Env) -> None:
    """Four vendor calls in flight hold the ``PASSTHROUGH_SLOTS``: a fifth waits until one ends,
    and a reuse takes no slot meanwhile. The vendor holds each transcript call until released."""
    assert PASSTHROUGH_SLOTS == 4
    entered = threading.Semaphore(0)
    release = threading.Event()
    called: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/earning-call-transcript"):
            called.append(f"{request.url.params['year']}-Q{request.url.params['quarter']}")
            entered.release()
            release.wait(5)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(answer)
    http = VendorHttp(fmp_api.BASE_URL, [FMP_KEY], env.policy.refresh, transport=transport)
    passthrough = Passthrough(Fmp(http, FMP_KEY), env.connect, env.policy, env.clock, (FMP_KEY,))
    passthrough.fetch("news", "ACME", {})  # stored: the next one is a reuse
    asks = [("2026", "1"), ("2026", "2"), ("2026", "3"), ("2026", "4"), ("2025", "4")]
    answered: list[bool] = []

    def fetch(kind: str, params: dict[str, str]) -> None:
        [fetched] = passthrough.fetch(kind, "ACME", params).values()
        answered.append(fetched.reused)

    calls = [
        threading.Thread(target=fetch, args=("transcript", {"year": y, "quarter": q}))
        for y, q in asks
    ]
    try:
        for thread in calls[:4]:
            thread.start()
        for _ in range(4):
            assert entered.acquire(timeout=5)
        calls[4].start()
        calls[4].join(0.2)
        assert calls[4].is_alive() and len(called) == 4  # the fifth waits for a slot
        reuse = threading.Thread(target=fetch, args=("news", {}))
        reuse.start()
        reuse.join(5)
        assert not reuse.is_alive() and answered == [True]  # a reuse needs no slot
        release.set()
        for thread in calls:
            thread.join(5)
    finally:
        release.set()
        http.close()
    assert not any(thread.is_alive() for thread in calls)
    assert sorted(called) == ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"]
    assert answered == [True] + [False] * 5
