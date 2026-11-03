"""The one HTTP client both vendor adapters use: bounded in time, redirect-refusing, key-scrubbing.

``VendorHttp.get`` makes up to ``policy.attempts`` tries, each in a slot of the client's
``RateLimiter``, which every thread calling through the client shares (``calls_per_minute``; 0 is
no pacing). It retries a transport error and the statuses 408, 429, 500, 502, 503 and 504. After a
429 it holds the limiter, so that every thread waits, for the numeric ``Retry-After`` or else
``policy.rate_limit_hold_s``, and sleeps that hold before the retry; after the others it sleeps the
policy's backoff (or a numeric ``Retry-After`` smaller than the time left). Any other failure, a
redirect included, is final on the first try: a redirect is refused before it can carry a
credential anywhere.

The deadline (``policy.deadline_s`` from the start of the call, extended by each wait for a slot
and each hold) bounds the whole call. No sleep is made that would leave under 0.1 s, no try is
sent with under 0.1 s left, each try's timeouts are capped at the time left, and the body is read
in chunks with the clock checked after each one. httpx's timeouts still apply per phase and per
socket read, so a call can overrun: by one capped read window while a body drips in, by one capped
window per slow phase (connect, send, headers) of its last try, and without a bound here if a
server drips its headers. The refresh layer's per-item bound is the last resort.

Every URL, log line and ``VendorError`` message this module makes passes through ``scrub``. httpx
and httpcore log raw URLs and headers themselves; a filter on each of their loggers scrubs the
secrets of every open client from their records, whatever levels and handlers the application's
logging configuration sets.
"""

import json
import logging
import math
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from types import TracebackType
from typing import Any, Self

import httpx

from fairband.config import utcnow
from fairband.policy import RefreshPolicy
from fairband.vendors.limiter import RateLimiter
from fairband.vendors.scrub import scrub

logger = logging.getLogger("fairband.vendors")

_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_DETAIL_CHARS = 200
_MIN_WINDOW_S = 0.1  # the least time left that a try is sent with
# httpx logs each request URL at INFO; httpcore logs response headers (a redirect's Location among
# them) at DEBUG. A logger's filters do not apply to its children's records, so each httpcore
# logger is named, and the parent too in case anything logs there.
_THIRD_PARTY_LOGGERS = (
    "httpx",
    "httpcore",
    "httpcore.connection",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
    "httpcore.socks",
)

_live_secrets: Counter[str] = Counter()  # each open client's secrets, counted per client
_live_lock = threading.Lock()


class _ScrubLiveSecrets(logging.Filter):
    """Rewrites a record so that its message has every open client's secrets scrubbed."""

    def filter(self, record: logging.LogRecord) -> bool:
        with _live_lock:
            secrets = tuple(_live_secrets)
        if secrets:
            # A bad format keeps the bare text: a filter must not raise into the code that logged.
            try:
                message = record.getMessage()
            except (TypeError, ValueError, KeyError):
                message = str(record.msg)
            record.msg, record.args = scrub(message, secrets), ()
        return True


_SCRUB_FILTER = _ScrubLiveSecrets()


def _register(secrets: Sequence[str]) -> None:
    with _live_lock:
        _live_secrets.update(secrets)
    for name in _THIRD_PARTY_LOGGERS:
        logging.getLogger(name).addFilter(_SCRUB_FILTER)  # a no-op once attached


def _unregister(secrets: Sequence[str]) -> None:
    with _live_lock:
        _live_secrets.subtract(secrets)
        for secret in secrets:
            if _live_secrets[secret] <= 0:
                del _live_secrets[secret]


class VendorError(Exception):
    """A failed vendor call. The message is scrubbed; ``status`` is ``None`` when none came back."""

    def __init__(self, message: str, status: int | None, retryable: bool) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


@dataclass(frozen=True)
class VendorResponse:
    """A 2xx response.

    ``json`` is the parsed body of a 200 whose content type names JSON, or whose body, under
    another content type, starts with ``{`` or ``[`` and parses; else ``None``. ``text`` is the
    body as received and is not scrubbed: these vendors never echo the key in a body, and the caller
    scrubs the payload before storing it. ``url`` is scrubbed. ``observed_at`` is the clock at the
    start of the successful try; ``attempts`` counts the tries.
    """

    status: int
    json: Any
    text: str
    url: str
    observed_at: datetime
    attempts: int


type _Failure = tuple[VendorError, float | None]  # the error and the Retry-After seconds, if any


class VendorHttp:
    """GETs under ``base_url`` with the policy's timeouts, retries and deadline.

    One ``httpx.Client`` per instance: redirects are not followed, TLS is verified and the
    environment (proxies, certificates, netrc) is ignored. ``secrets`` are scrubbed from everything
    this client emits, and from httpx's and httpcore's log records until ``close``. ``limiter``
    paces the tries at ``calls_per_minute`` on the client's clock and sleep. Close it, or use it as
    a context manager.
    """

    def __init__(
        self,
        base_url: str,
        secrets: Sequence[str],
        policy: RefreshPolicy,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = utcnow,
        calls_per_minute: float = 0.0,
    ) -> None:
        self._secrets = tuple(secret for secret in secrets if secret)
        self._policy = policy
        self._sleep = sleep
        self._clock = clock
        self.limiter = RateLimiter(calls_per_minute, clock, sleep)
        self._client = httpx.Client(
            base_url=base_url,
            transport=transport,
            follow_redirects=False,
            trust_env=False,
            verify=True,
            timeout=httpx.Timeout(
                connect=policy.connect_timeout_s,
                read=policy.read_timeout_s,
                write=policy.connect_timeout_s,
                pool=policy.connect_timeout_s,
            ),
        )
        _register(self._secrets)
        self._open = True

    def close(self) -> None:
        self._client.close()
        if self._open:
            self._open = False
            _unregister(self._secrets)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def get(self, path: str, params: Mapping[str, str]) -> VendorResponse:
        """GET ``path`` with ``params``; raises ``VendorError`` when no try succeeds in time."""
        # A wait for a slot or a hold is not the call's time: each extends the deadline.
        deadline = self._clock() + timedelta(seconds=self._policy.deadline_s)
        deadline += timedelta(seconds=self.limiter.acquire())
        attempt = 1
        outcome = self._attempt(path, params, attempt, deadline)
        while not isinstance(outcome, VendorResponse):
            failure, retry_after = outcome
            # Raised here, outside any except block, so no httpx exception (whose message may
            # carry the raw URL) is chained to it.
            if not failure.retryable or attempt >= self._policy.attempts:
                raise failure
            remaining = self._seconds_left(deadline)
            if failure.status == HTTPStatus.TOO_MANY_REQUESTS:
                delay = self._policy.rate_limit_hold_s if retry_after is None else retry_after
                self.limiter.hold(delay)
                deadline += timedelta(seconds=delay)
                remaining += delay
            else:
                delay = self._backoff(attempt)
                if retry_after is not None and retry_after < remaining:
                    delay = retry_after
            if remaining - delay < _MIN_WINDOW_S:
                raise self._out_of_time(failure)
            self._log(logging.WARNING, f"{failure}; retrying in {delay:g} s")
            self._sleep(delay)
            if self._seconds_left(deadline) < _MIN_WINDOW_S:  # the sleep overran
                raise self._out_of_time(failure)
            attempt += 1
            deadline += timedelta(seconds=self.limiter.acquire())
            outcome = self._attempt(path, params, attempt, deadline)
        return outcome

    def _attempt(
        self, path: str, params: Mapping[str, str], attempt: int, deadline: datetime
    ) -> VendorResponse | _Failure:
        """One try: the response on a 2xx, else the error and any Retry-After seconds."""
        timeout = self._timeout(max(self._seconds_left(deadline), _MIN_WINDOW_S))
        request = self._client.build_request("GET", path, params=params, timeout=timeout)
        url = str(request.url)  # raw: _log, _error and VendorResponse scrub it
        tag = f"attempt {attempt}/{self._policy.attempts}"
        began = self._clock()
        try:
            response = self._client.send(request, stream=True)
            try:
                body, whole = self._read(response, deadline)
            finally:
                response.close()
        except httpx.RequestError as exc:
            name = type(exc).__name__
            self._log(logging.INFO, f"GET {url} -> {name} ({self._ms_since(began)} ms, {tag})")
            what = f"{name}: {exc}" if str(exc) else name
            retryable = isinstance(exc, httpx.TransportError)
            return self._error(f"GET {url} -> {what} ({tag})", None, retryable), None
        status = response.status_code
        self._log(logging.INFO, f"GET {url} -> {status} ({self._ms_since(began)} ms, {tag})")
        what = f"{status} {response.reason_phrase}"
        text = body.decode(response.encoding or "utf-8", errors="replace")
        if response.is_success:
            if not whole:
                message = (
                    f"GET {url} -> {what}; the body was still arriving at the deadline ({tag})"
                )
                return self._error(message, status, retryable=True), None
            data: Any = None
            if status == 200:
                try:
                    data = _json(response.headers.get("Content-Type", ""), body)
                except ValueError:
                    message = f"GET {url} -> {what} with a body that is not JSON ({tag})"
                    return self._error(message, status, retryable=False), None
            return VendorResponse(status, data, text, self._scrub(url), began, attempt)
        if status in _RETRYABLE_STATUSES:
            failure = self._error(f"GET {url} -> {what} ({tag})", status, retryable=True)
            return failure, _retry_after(response)
        if 300 <= status < 400:
            what += ": redirect refused"
        # The body names the refusal (a plan limit, a bad symbol). It is scrubbed before it is
        # cut, so a cut cannot leave part of a key behind.
        elif detail := " ".join(self._scrub(text).split())[:_DETAIL_CHARS]:
            what += f": {detail}"
        return self._error(f"GET {url} -> {what} ({tag})", status, retryable=False), None

    def _read(self, response: httpx.Response, deadline: datetime) -> tuple[bytes, bool]:
        """The body and whether it is whole: reading stops at the first chunk past the deadline."""
        chunks: list[bytes] = []
        for chunk in response.iter_bytes():
            chunks.append(chunk)
            if self._clock() >= deadline:
                return b"".join(chunks), False
        return b"".join(chunks), True

    def _timeout(self, window_s: float) -> httpx.Timeout:
        """The policy's timeouts, each capped at ``window_s``."""
        connect_s = min(self._policy.connect_timeout_s, window_s)
        read_s = min(self._policy.read_timeout_s, window_s)
        return httpx.Timeout(connect=connect_s, read=read_s, write=connect_s, pool=connect_s)

    def _backoff(self, attempt: int) -> float:
        """The sleep after try ``attempt``; the last policy value repeats."""
        backoff = self._policy.backoff_s
        return backoff[min(attempt, len(backoff)) - 1] if backoff else 0.0

    def _out_of_time(self, failure: VendorError) -> VendorError:
        message = f"{failure}; the {self._policy.deadline_s:g} s deadline leaves no time to retry"
        return self._error(message, failure.status, retryable=True)

    def _seconds_left(self, deadline: datetime) -> float:
        return (deadline - self._clock()).total_seconds()

    def _ms_since(self, began: datetime) -> int:
        return round((self._clock() - began).total_seconds() * 1000)

    def _scrub(self, text: str) -> str:
        return scrub(text, self._secrets)

    def _log(self, level: int, message: str) -> None:
        logger.log(level, "%s", self._scrub(message))

    def _error(self, message: str, status: int | None, retryable: bool) -> VendorError:
        return VendorError(self._scrub(message), status, retryable)


def _json(content_type: str, body: bytes) -> Any:
    """The parsed body when ``content_type`` names JSON, or when the body, under another type,
    starts with ``{`` or ``[`` and parses; else ``None``. Declared JSON that does not parse raises
    ``ValueError``.
    """
    if "json" in content_type.lower():
        return json.loads(body)
    if body.lstrip()[:1] in (b"{", b"["):
        try:
            return json.loads(body)
        except ValueError:
            return None
    return None


def _retry_after(response: httpx.Response) -> float | None:
    """``Retry-After`` in seconds when it is a non-negative number; an HTTP date is ignored."""
    try:
        seconds = float(response.headers.get("Retry-After", ""))
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None
