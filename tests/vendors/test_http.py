"""The vendor HTTP client against a scripted ``httpx.MockTransport``; never the network.

``FakeTime`` is the clock and the sleep: time moves only when the client sleeps or a scripted
request takes time, so the backoff and the deadline are exact.
"""

import logging
import logging.config
import traceback
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from fairband.policy import RefreshPolicy, load_policy
from fairband.vendors.http import VendorError, VendorHttp, VendorResponse

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
FMP_BASE = "https://fmp.example/stable"
FMP_PARAMS = {"symbol": "AAPL", "apikey": "SECRET123"}

type Reply = (
    int | httpx.Response | type[httpx.TransportError] | Callable[[httpx.Request], httpx.Response]
)


class FakeTime:
    def __init__(self, oversleep_s: float = 0) -> None:
        self.now = T0
        self.sleeps: list[float] = []
        self.oversleep_s = oversleep_s

    def clock(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += timedelta(seconds=seconds + self.oversleep_s)


class Script:
    """Answers the n-th request with the n-th reply (the last one repeats) and keeps the requests.

    A reply is a status, a response, a transport error class raised with the request URL in its
    message (as httpx's own errors may carry it), or a function of the request.
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
        if isinstance(reply, type):
            raise reply(f"cannot reach {request.url}", request=request)
        return reply(request)


def slow_server(time: FakeTime, natural_s: float) -> Callable[[httpx.Request], httpx.Response]:
    """Answers 503 after ``natural_s``, or times out at the try's read window if that is sooner."""

    def reply(request: httpx.Request) -> httpx.Response:
        read_s = request.extensions["timeout"]["read"]
        time.now += timedelta(seconds=min(natural_s, read_s))
        if natural_s > read_s:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(503)

    return reply


class Drip(httpx.SyncByteStream):
    """A body that sends a byte every ``every_s`` seconds, each inside its read window.

    It ends after ``count`` bytes, so a client that reads it to the end fails the test instead of
    hanging it.
    """

    def __init__(self, time: FakeTime, every_s: float, count: int = 20) -> None:
        self.time = time
        self.every_s = every_s
        self.count = count

    def __iter__(self) -> Iterator[bytes]:
        for _ in range(self.count):
            self.time.now += timedelta(seconds=self.every_s)
            yield b" "


@pytest.fixture
def policy() -> RefreshPolicy:
    return load_policy().refresh


def _client(
    script: Script,
    policy: RefreshPolicy,
    time: FakeTime | None = None,
    base_url: str = FMP_BASE,
    secrets: Sequence[str] = ("SECRET123",),
    calls_per_minute: float = 0.0,
) -> VendorHttp:
    time = time or script.time or FakeTime()
    return VendorHttp(
        base_url,
        secrets,
        policy,
        transport=script.transport,
        sleep=time.sleep,
        clock=time.clock,
        calls_per_minute=calls_per_minute,
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
    # The root at DEBUG: httpx and httpcore, which set no level of their own, log here too.
    caplog.set_level(logging.DEBUG)
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
    assert any(record.name == "httpx" for record in caplog.records)  # httpx's own request lines
    assert secret not in caplog.text
    assert all(secret not in record.getMessage() for record in caplog.records)


@pytest.fixture
def restore_httpx_logger() -> Iterator[None]:
    logger = logging.getLogger("httpx")
    level, handlers, propagate, disabled = (
        logger.level,
        logger.handlers[:],
        logger.propagate,
        logger.disabled,
    )
    yield
    logger.setLevel(level)
    logger.handlers[:] = handlers
    logger.propagate, logger.disabled = propagate, disabled


@pytest.mark.usefixtures("restore_httpx_logger")
def test_httpx_lines_scrubbed_when_logging_is_configured_later(policy: RefreshPolicy) -> None:
    seen: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record)

    with _client(Script(200), policy) as http:
        # The app's own startup order: its logging configuration comes after the client exists.
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {"capture": {"()": Capture}},
                "loggers": {"httpx": {"level": "INFO", "handlers": ["capture"]}},
            }
        )
        http.get("/quote", FMP_PARAMS)
    messages = [record.getMessage() for record in seen]
    assert any(m.startswith("HTTP Request: GET") and "apikey=<key>" in m for m in messages)
    assert not any("SECRET123" in m for m in messages)


def test_httpcore_records_scrubbed(caplog: pytest.LogCaptureFixture, policy: RefreshPolicy) -> None:
    caplog.set_level(logging.DEBUG, logger="httpcore.http11")
    headers = [(b"Location", b"https://elsewhere.example/?apikey=SECRET123")]
    with _client(Script(200), policy):
        logging.getLogger("httpcore.http11").debug(
            "receive_response_headers.complete return_value=%r",
            (b"HTTP/1.1", 302, b"Found", headers),
        )
    [record] = [r for r in caplog.records if r.name == "httpcore.http11"]
    assert "SECRET123" not in record.getMessage() and "apikey=<key>" in record.getMessage()


def test_every_httpx_and_httpcore_logger_scrubs(
    caplog: pytest.LogCaptureFixture, policy: RefreshPolicy
) -> None:
    caplog.set_level(logging.DEBUG)
    # The real transport imports httpcore, which makes its loggers; a new one fails this test.
    with VendorHttp(FMP_BASE, ["SECRET123"], policy):
        names = [
            name
            for name, logger in logging.Logger.manager.loggerDict.items()
            if isinstance(logger, logging.Logger) and name.split(".")[0] in ("httpx", "httpcore")
        ]
        for name in names:
            logging.getLogger(name).error("GET %s", "https://x.example/?apikey=SECRET123")
    assert {"httpx", "httpcore.connection", "httpcore.http11"} <= set(names)
    assert len(caplog.records) == len(names)
    assert "SECRET123" not in caplog.text


def test_secret_scrubbed_until_its_last_client_closes(
    caplog: pytest.LogCaptureFixture, policy: RefreshPolicy
) -> None:
    caplog.set_level(logging.DEBUG, logger="httpcore.http11")
    log = logging.getLogger("httpcore.http11")
    first, second = _client(Script(200), policy), _client(Script(200), policy)
    first.close()
    first.close()  # a second close must not release the other client's registration
    log.debug("still open: %s", "SECRET123")
    second.close()
    log.debug("all closed: %s", "SECRET123")
    assert [r.getMessage() for r in caplog.records] == [
        "still open: <key>",
        "all closed: SECRET123",
    ]


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
    # The 429 holds for the policy's 60 s; the 503 backs off the second step's 4 s.
    assert time.sleeps == [policy.rate_limit_hold_s, 4] == [60, 4]
    # The third attempt starts after two 0.25 s requests and the 60 s and 4 s sleeps.
    assert response.observed_at == T0 + timedelta(seconds=64.5)
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


@pytest.mark.parametrize("natural_s", [5, 13, 16, 26, 40])
def test_deadline_bounds_the_whole_call(policy: RefreshPolicy, natural_s: float) -> None:
    # Each try lasts natural_s or until its read window closes. With every window capped at the
    # time left, the call ends by the deadline; uncapped, a 16 s try would end the call at 32 s.
    time = FakeTime()
    script = Script(slow_server(time, natural_s))
    with _client(script, policy, time) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert caught.value.retryable is True
    assert time.now - T0 <= timedelta(seconds=policy.deadline_s)


def test_each_try_gets_at_most_the_time_left(policy: RefreshPolicy) -> None:
    time = FakeTime()
    script = Script(503, 200, time=time, takes_s=26)
    with _client(script, policy) as http:
        http.get("/quote", FMP_PARAMS)
    # The first try has all 30 s; the second starts at 28 s (26 s try, 2 s sleep) with 2 s left.
    assert [r.extensions["timeout"] for r in script.requests] == [
        {"connect": 5, "read": 15, "write": 5, "pool": 5},
        {"connect": 2, "read": 2, "write": 2, "pool": 2},
    ]


def test_no_try_starts_at_the_deadline(policy: RefreshPolicy) -> None:
    # A 28 s try leaves 2 s: the 2 s sleep would end exactly at the deadline.
    time = FakeTime()
    script = Script(503, time=time, takes_s=28)
    with _client(script, policy) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert len(script.requests) == 1 and time.sleeps == []
    assert caught.value.status == 503 and caught.value.retryable is True


def test_no_sleep_that_leaves_under_a_tenth_of_a_second(policy: RefreshPolicy) -> None:
    # A 27.95 s try leaves 2.05 s; after the 2 s sleep, 0.05 s would be too little to send.
    time = FakeTime()
    script = Script(503, time=time, takes_s=27.95)
    with _client(script, policy) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert len(script.requests) == 1 and time.sleeps == []
    assert caught.value.status == 503 and caught.value.retryable is True


def test_no_try_with_under_a_tenth_of_a_second_left(policy: RefreshPolicy) -> None:
    # A 27.8 s try leaves 2.2 s; the 2 s sleep overruns by 0.15 s and leaves 0.05 s.
    time = FakeTime(oversleep_s=0.15)
    script = Script(503, time=time, takes_s=27.8)
    with _client(script, policy) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert len(script.requests) == 1 and time.sleeps == [2]
    assert caught.value.status == 503 and caught.value.retryable is True


def test_slow_drip_body_cut_at_the_deadline(policy: RefreshPolicy) -> None:
    # A byte every 14 s never trips the 15 s read window; the client stops reading at the first
    # byte past the deadline, so the call overruns by less than one read window.
    time = FakeTime()
    drip = httpx.Response(200, headers={"Content-Type": "application/json"}, stream=Drip(time, 14))
    script = Script(drip)
    with _client(script, policy, time) as http, pytest.raises(VendorError) as caught:
        http.get("/quote", FMP_PARAMS)
    assert len(script.requests) == 1
    assert caught.value.status == 200 and caught.value.retryable is True
    assert time.now - T0 <= timedelta(seconds=policy.deadline_s + policy.read_timeout_s)


@pytest.mark.parametrize(
    ("retry_after", "slept"),
    [("1", 1.0), ("120", 2), ("Sun, 01 Nov 2026 09:31:00 GMT", 2)],
    ids=["within-deadline", "past-deadline", "not-a-number"],
)
def test_retry_after_honored_within_deadline(
    policy: RefreshPolicy, retry_after: str, slept: float
) -> None:
    # On a retryable status other than 429 (which holds instead; see below), a numeric
    # Retry-After replaces the backoff when it ends within the deadline.
    time = FakeTime()
    script = Script(httpx.Response(503, headers={"Retry-After": retry_after}), 200)
    with _client(script, policy, time) as http:
        assert http.get("/quote", FMP_PARAMS).attempts == 2
    assert time.sleeps == [slept]


def test_every_try_takes_a_slot(policy: RefreshPolicy) -> None:
    # At 60 a minute the first try takes the slot at t = 0 and answers 500. The retry sleeps the
    # 2 s backoff, past the slot at t = 1, and takes the slot at t = 2; so the next call waits
    # for t = 3, one slot after the retry's.
    time = FakeTime()
    script = Script(500, 200, time=time)
    with _client(script, policy, calls_per_minute=60) as http:
        first = http.get("/quote", FMP_PARAMS)
        second = http.get("/quote", FMP_PARAMS)
    assert first.attempts == 2 and first.observed_at == T0 + timedelta(seconds=2)
    assert second.attempts == 1 and second.observed_at == T0 + timedelta(seconds=3)
    assert time.sleeps == [2, 1]


def test_a_429_holds_the_limiter_for_the_policy_hold(policy: RefreshPolicy) -> None:
    # At 60 a minute the first try answers 429 at t = 0 with no Retry-After: the limiter is held
    # for the policy's hold and the retry sleeps it. Another worker's call arrives 10 s into the
    # hold and waits out the rest; it takes the hold's first slot and the retry the one after.
    hold = policy.rate_limit_hold_s
    time = FakeTime()
    script = Script(429, 200, time=time)
    meanwhile: list[VendorResponse] = []

    def sleep(seconds: float) -> None:
        wake = time.now + timedelta(seconds=seconds)
        time.sleeps.append(seconds)
        if len(time.sleeps) == 1:  # the hold: the other worker calls while it runs
            time.now += timedelta(seconds=10)
            meanwhile.append(http.get("/quote", FMP_PARAMS))
        time.now = max(time.now, wake)

    with VendorHttp(
        FMP_BASE,
        ["SECRET123"],
        policy,
        transport=script.transport,
        sleep=sleep,
        clock=time.clock,
        calls_per_minute=60,
    ) as http:
        response = http.get("/quote", FMP_PARAMS)
    assert time.sleeps == [hold, hold - 10, 1]
    assert [other.observed_at for other in meanwhile] == [T0 + timedelta(seconds=hold)]
    assert response.attempts == 2 and response.observed_at == T0 + timedelta(seconds=hold + 1)
    assert len(script.requests) == 3


@pytest.mark.parametrize("seconds", [7, 120], ids=["within-deadline", "past-deadline"])
def test_a_429_with_a_numeric_retry_after_holds_that_long(
    policy: RefreshPolicy, seconds: int
) -> None:
    # The hold extends the deadline by its length, so one past the 30 s still gets its retry.
    time = FakeTime()
    reply = httpx.Response(429, headers={"Retry-After": str(seconds)})
    script = Script(reply, 200, time=time)
    with _client(script, policy, calls_per_minute=60) as http:
        response = http.get("/quote", FMP_PARAMS)
    assert response.attempts == 2 and response.observed_at == T0 + timedelta(seconds=seconds)
    assert time.sleeps == [seconds]


def test_a_429_with_an_http_date_retry_after_holds_the_default(policy: RefreshPolicy) -> None:
    time = FakeTime()
    reply = httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    script = Script(reply, 200, time=time)
    with _client(script, policy, calls_per_minute=60) as http:
        response = http.get("/quote", FMP_PARAMS)
    hold = policy.rate_limit_hold_s
    assert response.attempts == 2 and response.observed_at == T0 + timedelta(seconds=hold)
    assert time.sleeps == [hold]


def test_limiter_waits_do_not_count_against_the_deadline(policy: RefreshPolicy) -> None:
    # Another worker's 429 has held the limiter to t = 55. The call is admitted then with its
    # whole deadline ahead: each try gets the policy's full timeouts, and a 429 with
    # Retry-After: 1 is retried at t = 56, long after the 30 s from the call's start.
    time = FakeTime()
    script = Script(httpx.Response(429, headers={"Retry-After": "1"}), 200, time=time)
    with _client(script, policy, calls_per_minute=60) as http:
        http.limiter.hold(55)
        response = http.get("/quote", FMP_PARAMS)
    assert response.attempts == 2 and response.observed_at == T0 + timedelta(seconds=56)
    assert time.sleeps == [55, 1]
    full = {"connect": 5, "read": 15, "write": 5, "pool": 5}
    assert [r.extensions["timeout"] for r in script.requests] == [full, full]


def test_three_429s_still_fail_the_call(policy: RefreshPolicy) -> None:
    time = FakeTime()
    script = Script(429, time=time)
    with (
        _client(script, policy, calls_per_minute=60) as http,
        pytest.raises(VendorError) as caught,
    ):
        http.get("/quote", FMP_PARAMS)
    assert caught.value.status == 429 and caught.value.retryable is True
    assert "429 Too Many Requests (attempt 3/3)" in str(caught.value)
    hold = policy.rate_limit_hold_s
    assert len(script.requests) == 3 and time.sleeps == [hold, hold]


@pytest.mark.parametrize(
    ("content_type", "body", "parsed"),
    [
        ("application/json; charset=utf-8", '{"a": 1}', {"a": 1}),
        ("application/vnd.api+json", "[1]", [1]),
        ("text/html; charset=utf-8", ' \n[{"a": 1}]', [{"a": 1}]),
        ("text/html", "[not json", None),
        ("text/csv", "a,b\n1,2", None),
    ],
    ids=["json", "json-suffix", "json-as-html", "bracket-not-json", "csv"],
)
def test_json_parsed_when_declared_or_sniffed(
    policy: RefreshPolicy, content_type: str, body: str, parsed: object
) -> None:
    reply = httpx.Response(200, text=body, headers={"Content-Type": content_type})
    with _client(Script(reply), policy) as http:
        response = http.get("/quote", FMP_PARAMS)
    assert response.json == parsed and response.text == body


def test_declared_json_that_does_not_parse_is_refused(policy: RefreshPolicy) -> None:

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
