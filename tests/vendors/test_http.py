"""The vendor HTTP client against a scripted ``httpx.MockTransport``; never the network.

``FakeTime`` is the clock and the sleep: time moves only when the client sleeps or a scripted
request takes time, so the backoff and the deadline are exact.
"""

import logging
import traceback
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from fairband.policy import RefreshPolicy, load_policy
from fairband.vendors.http import VendorError, VendorHttp

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
FMP_BASE = "https://fmp.example/stable"
FMP_PARAMS = {"symbol": "AAPL", "apikey": "SECRET123"}

type Reply = int | httpx.Response | type[httpx.TransportError]


class FakeTime:
    def __init__(self) -> None:
        self.now = T0
        self.sleeps: list[float] = []

    def clock(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += timedelta(seconds=seconds)


class Script:
    """Answers the n-th request with the n-th reply (the last one repeats) and keeps the requests.

    A reply is a status, a response, or a transport error class raised with the request URL in
    its message, as httpx's own errors may carry it.
    """

    def __init__(self, *replies: Reply, time: FakeTime | None = None, takes_s: float = 0) -> None:
        self.replies = replies
        self.time = time
        self.takes_s = takes_s
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.time is not None:
            self.time.now += timedelta(seconds=self.takes_s)
        reply = self.replies[min(len(self.requests), len(self.replies)) - 1]
        if isinstance(reply, int):
            return httpx.Response(reply)
        if isinstance(reply, httpx.Response):
            return reply
        raise reply(f"cannot reach {request.url}", request=request)


@pytest.fixture
def policy() -> RefreshPolicy:
    return load_policy().refresh


def _client(
    script: Script,
    policy: RefreshPolicy,
    time: FakeTime | None = None,
    base_url: str = FMP_BASE,
    secrets: Sequence[str] = ("SECRET123",),
) -> VendorHttp:
    time = time or script.time or FakeTime()
    return VendorHttp(
        base_url, secrets, policy, transport=script.transport, sleep=time.sleep, clock=time.clock
    )


def _vendor_lines(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == "fairband.vendors"]


@pytest.mark.parametrize(
    ("base_url", "path", "params", "secret"),
    [
        (FMP_BASE, "/quote", FMP_PARAMS, "SECRET123"),
        ("https://gf.example/public/user/T0K3N", "/stock/AAPL/summary", {}, "T0K3N"),
    ],
    ids=["query-key", "path-token"],
)
def test_key_never_in_response_url_or_logs(
    caplog: pytest.LogCaptureFixture,
    policy: RefreshPolicy,
    base_url: str,
    path: str,
    params: dict[str, str],
    secret: str,
) -> None:
    caplog.set_level(logging.DEBUG)  # every logger, httpx's own included
    ok = Script(httpx.Response(200, json={"symbol": "AAPL"}))
    with _client(ok, policy, base_url=base_url, secrets=[secret]) as http:
        response = http.get(path, params)
    assert secret in str(ok.requests[0].url)  # the vendor still receives the key
    assert secret not in response.url and "<key>" in response.url

    failing = Script(500)
    with (
        _client(failing, policy, base_url=base_url, secrets=[secret]) as http,
        pytest.raises(VendorError) as caught,
    ):
        http.get(path, params)
    assert "<key>" in str(caught.value) and secret not in str(caught.value)

    assert _vendor_lines(caplog)
    assert secret not in caplog.text
    assert all(secret not in record.getMessage() for record in caplog.records)


def test_transport_errors_retried_then_raised_scrubbed(
    caplog: pytest.LogCaptureFixture, policy: RefreshPolicy
) -> None:
    caplog.set_level(logging.DEBUG)
    script = Script(httpx.ConnectError)
    time = FakeTime()
    with _client(script, policy, time) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    error = caught.value
    assert len(script.requests) == 3 and time.sleeps == [2, 4]
    assert error.status is None and error.retryable is True
    assert "cannot reach" in str(error) and "<key>" in str(error)
    # No chained httpx exception rides along to leak the raw URL in a traceback.
    assert error.__cause__ is None and error.__context__ is None
    assert "SECRET123" not in "".join(traceback.format_exception(error))
    assert "SECRET123" not in caplog.text


def test_retries_then_succeeds(caplog: pytest.LogCaptureFixture, policy: RefreshPolicy) -> None:
    caplog.set_level(logging.INFO)
    time = FakeTime()
    script = Script(429, 503, httpx.Response(200, json=[1]), time=time, takes_s=0.25)
    with _client(script, policy) as http:
        response = http.get("/quote", FMP_PARAMS)
    assert response.status == 200 and response.json == [1] and response.text == "[1]"
    assert response.attempts == 3 and len(script.requests) == 3
    assert time.sleeps == [2, 4]
    # The third attempt starts after two 0.25 s requests and the 2 s and 4 s sleeps.
    assert response.observed_at == T0 + timedelta(seconds=6.5)
    url = "https://fmp.example/stable/quote?symbol=AAPL&apikey=<key>"
    assert response.url == url
    lines = _vendor_lines(caplog)
    assert [level for level, _ in lines] == [
        logging.INFO,
        logging.WARNING,
        logging.INFO,
        logging.WARNING,
        logging.INFO,
    ]
    assert lines[0][1] == f"GET {url} -> 429 (250 ms, attempt 1/3)"
    assert lines[4][1] == f"GET {url} -> 200 (250 ms, attempt 3/3)"


def test_no_retry_on_402(policy: RefreshPolicy) -> None:
    script = Script(httpx.Response(402, text="Payment required"))
    time = FakeTime()
    with _client(script, policy, time) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert caught.value.status == 402 and caught.value.retryable is False
    assert len(script.requests) == 1 and time.sleeps == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 501])
def test_no_retry_on_other_refusals(policy: RefreshPolicy, status: int) -> None:
    script = Script(status)
    with _client(script, policy) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert caught.value.status == status and caught.value.retryable is False
    assert len(script.requests) == 1


def test_redirect_refused(policy: RefreshPolicy) -> None:
    # The Location carries the key, as a vendor's redirect would keep the query string.
    moved = httpx.Response(302, headers={"Location": "https://elsewhere.example/?apikey=SECRET123"})
    script = Script(moved, 200)
    with _client(script, policy) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert caught.value.status == 302 and caught.value.retryable is False
    assert len(script.requests) == 1
    assert "SECRET123" not in str(caught.value)


def test_deadline_bounds_retries(policy: RefreshPolicy) -> None:
    # Each request takes 13 s: attempt 1 ends at 13 s, the 2 s sleep ends at 15 s, attempt 2 ends
    # at 28 s, and the 4 s sleep would end past the 30 s deadline.
    time = FakeTime()
    script = Script(503, time=time, takes_s=13)
    with _client(script, policy) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert len(script.requests) == 2 and time.sleeps == [2]
    assert caught.value.status == 503 and caught.value.retryable is True


@pytest.mark.parametrize(
    ("retry_after", "slept"),
    [("1", 1.0), ("120", 2), ("Sun, 01 Nov 2026 09:31:00 GMT", 2)],
    ids=["within-deadline", "past-deadline", "not-a-number"],
)
def test_retry_after_honored_within_deadline(
    policy: RefreshPolicy, retry_after: str, slept: float
) -> None:
    time = FakeTime()
    script = Script(httpx.Response(429, headers={"Retry-After": retry_after}), 200)
    with _client(script, policy, time) as http:
        assert http.get("/quote", FMP_PARAMS).attempts == 2
    assert time.sleeps == [slept]


def test_json_parsed_only_for_a_json_200(policy: RefreshPolicy) -> None:
    csv = httpx.Response(200, text="a,b\n1,2", headers={"Content-Type": "text/csv"})
    with _client(Script(csv), policy) as http:
        response = http.get("/quote", FMP_PARAMS)
    assert response.json is None and response.text == "a,b\n1,2"

    bad = httpx.Response(200, content=b"{oops", headers={"Content-Type": "application/json"})
    script = Script(bad)
    with _client(script, policy) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert caught.value.status == 200 and caught.value.retryable is False
    assert len(script.requests) == 1


def test_client_settings(policy: RefreshPolicy) -> None:
    with VendorHttp(FMP_BASE, ["SECRET123"], policy) as http:
        client = http._client
        assert client.follow_redirects is False and client.trust_env is False
        assert client.timeout == httpx.Timeout(connect=5, read=15, write=5, pool=5)
