"""The one HTTP client both vendor adapters use: bounded in time, redirect-refusing, key-scrubbing.

``VendorHttp.get`` makes up to ``policy.attempts`` tries. It retries a transport error and the
statuses 408, 429, 500, 502, 503 and 504, sleeping the policy's backoff between tries (or a numeric
``Retry-After`` smaller than the time left), and gives up when the next sleep would pass the call's
wall-clock deadline. The deadline governs retries; a try in flight is bounded by the httpx timeouts
alone. Any other failure, a redirect included, is final on the first try: a redirect is refused
before it can carry a credential anywhere. Every URL, log line and ``VendorError`` message passes
through ``scrub`` first, so the key never leaves this module in the clear.
"""

import logging
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Any, Self

import httpx

from fairband.config import utcnow
from fairband.policy import RefreshPolicy
from fairband.vendors.scrub import scrub

logger = logging.getLogger("fairband.vendors")

_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_DETAIL_CHARS = 200
# httpx logs every request URL, key included, at INFO; httpcore logs response headers (a
# redirect's Location among them) at DEBUG. Held at WARNING, the only request lines are ours.
_URL_LOGGERS = ("httpx", "httpcore")


class VendorError(Exception):
    """A failed vendor call. The message is scrubbed; ``status`` is ``None`` when none came back."""

    def __init__(self, message: str, status: int | None, retryable: bool) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


@dataclass(frozen=True)
class VendorResponse:
    """A 2xx response.

    ``json`` is the parsed body of a 200 with a JSON content type, else ``None``. ``text`` is the
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
    """GETs under ``base_url`` with the policy's timeouts and retries, scrubbing ``secrets``.

    One ``httpx.Client`` per instance: redirects are not followed, TLS is verified and the
    environment (proxies, certificates, netrc) is ignored. Close it, or use it as a context manager.
    Creating one sets the httpx and httpcore loggers to WARNING, since they log raw URLs.
    """

    def __init__(
        self,
        base_url: str,
        secrets: Sequence[str],
        policy: RefreshPolicy,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        for name in _URL_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
        self._secrets = tuple(secrets)
        self._policy = policy
        self._sleep = sleep
        self._clock = clock
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

    def close(self) -> None:
        self._client.close()

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
        """GET ``path`` with ``params``; raises ``VendorError`` when no try succeeds.

        The deadline runs from the first try; a retry whose sleep would end past it is not made.
        """
        start = self._clock()
        attempt = 0
        while True:
            attempt += 1
            outcome = self._attempt(path, params, attempt)
            if isinstance(outcome, VendorResponse):
                return outcome
            failure, retry_after = outcome
            # Raised here, outside any except block, so no httpx exception (whose message may
            # carry the raw URL) is chained to it.
            if not failure.retryable or attempt >= self._policy.attempts:
                raise failure
            remaining = self._policy.deadline_s - (self._clock() - start).total_seconds()
            delay = self._backoff(attempt)
            if retry_after is not None and retry_after < remaining:
                delay = retry_after
            if delay > remaining:
                raise self._error(
                    f"{failure}; the next try would pass the {self._policy.deadline_s:g} s"
                    " deadline",
                    failure.status,
                    retryable=True,
                )
            self._log(logging.WARNING, f"{failure}; retrying in {delay:g} s")
            self._sleep(delay)

    def _attempt(
        self, path: str, params: Mapping[str, str], attempt: int
    ) -> VendorResponse | _Failure:
        """One try: the response on a 2xx, else the error and any Retry-After seconds."""
        request = self._client.build_request("GET", path, params=params)
        url = str(request.url)  # raw: _log, _error and VendorResponse scrub it
        tag = f"attempt {attempt}/{self._policy.attempts}"
        began = self._clock()
        try:
            response = self._client.send(request)
        except httpx.RequestError as exc:
            name = type(exc).__name__
            self._log(logging.INFO, f"GET {url} -> {name} ({self._ms_since(began)} ms, {tag})")
            what = f"{name}: {exc}" if str(exc) else name
            retryable = isinstance(exc, httpx.TransportError)
            return self._error(f"GET {url} -> {what} ({tag})", None, retryable), None
        status = response.status_code
        self._log(logging.INFO, f"GET {url} -> {status} ({self._ms_since(began)} ms, {tag})")
        what = f"{status} {response.reason_phrase}"
        if response.is_success:
            body: Any = None
            if status == 200 and _is_json(response):
                try:
                    body = response.json()
                except ValueError:
                    message = f"GET {url} -> {what} with a body that is not JSON ({tag})"
                    return self._error(message, status, retryable=False), None
            return VendorResponse(status, body, response.text, self._scrub(url), began, attempt)
        if status in _RETRYABLE_STATUSES:
            failure = self._error(f"GET {url} -> {what} ({tag})", status, retryable=True)
            return failure, _retry_after(response)
        if 300 <= status < 400:
            what += ": redirect refused"
        # The body names the refusal (a plan limit, a bad symbol). It is scrubbed before it is
        # cut, so a cut cannot leave part of a key behind.
        elif detail := " ".join(self._scrub(response.text).split())[:_DETAIL_CHARS]:
            what += f": {detail}"
        return self._error(f"GET {url} -> {what} ({tag})", status, retryable=False), None

    def _backoff(self, attempt: int) -> float:
        """The sleep after try ``attempt``; the last policy value repeats."""
        backoff = self._policy.backoff_s
        return backoff[min(attempt, len(backoff)) - 1] if backoff else 0.0

    def _ms_since(self, began: datetime) -> int:
        return round((self._clock() - began).total_seconds() * 1000)

    def _scrub(self, text: str) -> str:
        return scrub(text, self._secrets)

    def _log(self, level: int, message: str) -> None:
        logger.log(level, "%s", self._scrub(message))

    def _error(self, message: str, status: int | None, retryable: bool) -> VendorError:
        return VendorError(self._scrub(message), status, retryable)


def _is_json(response: httpx.Response) -> bool:
    content_type: str = response.headers.get("Content-Type", "")
    media_type = content_type.split(";")[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def _retry_after(response: httpx.Response) -> float | None:
    """``Retry-After`` in seconds when it is a non-negative number; an HTTP date is ignored."""
    try:
        seconds = float(response.headers.get("Retry-After", ""))
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None
