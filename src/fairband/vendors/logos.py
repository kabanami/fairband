"""The company logo (B-203): the file's fetch from FMP's image host and its store in the data
folder.

``fetch_logo`` gets the file at an address ``profile_logo`` passed: FMP's image host answers
without a key, so the request carries none, and it counts against no quota. Like the vendor
client (``vendors.http``) it follows no redirect, which could lead to any host, and reads nothing
from the environment, so no proxy stands between. It asks for the body with no content encoding
and refuses an answer that has one: a PNG is compressed already, and an encoded body could
unpack past the size limit before the limit is checked. It takes a 200 whose body starts with
the PNG signature and holds at most ``MAX_BYTES``; anything else is a ``LogoError``, a transport
error and a timeout among them. Each phase of the request has httpx's timeout, five seconds to
connect and ten for each read; the whole fetch has no deadline of its own.

``Logos`` keeps one file a symbol, ``<SYMBOL>.png``, in its directory (``logos`` in the data
folder, outside the repository like every vendor file). ``file`` answers the stored file while it
is younger than ``MAX_AGE``, and asks nobody. A missing file is fetched and stored. A failed
fetch of a missing file answers ``None`` and stores nothing; the store remembers the failure in
memory and asks again ``RETRY_MISSING_AFTER`` later, sooner if the server starts again. A file of
``MAX_AGE`` or older is fetched again: a company changes its logo, and a ticker passes to another
company. Where that fetch fails the old file stays the answer and is next tried ``RETRY_AFTER``
later. Neither failure is tried again at each read: without the network every read would
otherwise wait for a fetch to fail, and nothing would bound how often the host is asked. Each
failure is one line in the log, the symbol and the reason. A file's age is its modification time
against the store's clock; a write sets it to the clock's now, through a temporary file that
replaces the old one whole.
"""

import logging
import os
import tempfile
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

MAX_BYTES = 512 * 1024  # FMP's logos are 250 px squares of 1 to 30 KB
MAX_AGE = timedelta(days=90)
RETRY_AFTER = timedelta(days=1)  # after a failed fetch of an old file, which stays the answer
RETRY_MISSING_AFTER = timedelta(minutes=10)  # after a failed fetch of a missing file
_PNG = b"\x89PNG\r\n\x1a\n"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class LogoError(Exception):
    """The fetch gave no logo: its sentence says why, and names no address."""


def logo_client(transport: httpx.BaseTransport | None) -> httpx.Client:
    """The client of one fetch: it follows no redirect, reads nothing from the environment and
    asks for no content encoding; ``transport`` is httpx's own unless a test gives one."""
    return httpx.Client(
        timeout=_TIMEOUT,
        follow_redirects=False,
        trust_env=False,
        headers={"Accept-Encoding": "identity"},
        transport=transport,
    )


def fetch_logo(url: str, transport: httpx.BaseTransport | None = None) -> bytes:
    """The PNG at ``url`` (the module docstring), through a ``logo_client`` of its own."""
    body = bytearray()
    try:
        with logo_client(transport) as client, client.stream("GET", url) as response:
            if response.status_code != httpx.codes.OK:
                raise LogoError(f"status {response.status_code}")
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise LogoError("an encoded body")
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise LogoError(f"over {MAX_BYTES} bytes")
    except httpx.HTTPError as exc:
        raise LogoError(type(exc).__name__) from None
    if not body.startswith(_PNG):
        raise LogoError("not a PNG")
    return bytes(body)


class Logos:
    """The logo files of ``directory``, fetched with ``get`` and aged on ``clock`` (the module
    docstring)."""

    def __init__(
        self, directory: Path, get: Callable[[str], bytes], clock: Callable[[], datetime]
    ) -> None:
        self._directory = directory
        self._get = get
        self._clock = clock
        self._failed: dict[str, float] = {}  # a symbol with no file: when its fetch last failed

    def file(self, symbol: str, url: str) -> Path | None:
        """The stored logo of ``symbol``, fetched from ``url`` when it is missing or old;
        ``None`` with no file and no fetch that gave one. ``symbol`` is a symbol in the exchange
        form, which holds no path separator."""
        path = self._directory / f"{symbol}.png"
        now = self._clock().timestamp()
        try:
            age = now - path.stat().st_mtime
        except FileNotFoundError:
            age = None
        if age is not None and age < MAX_AGE.total_seconds():
            return path
        failed = self._failed.get(symbol)
        waits = failed is not None and now - failed < RETRY_MISSING_AFTER.total_seconds()
        if age is None and waits:
            return None
        try:
            body = self._get(url)
        except LogoError as exc:
            logger.info("no logo for %s: %s", symbol, exc)
            if age is None:
                self._failed[symbol] = now
                return None
            retry_at = now - (MAX_AGE - RETRY_AFTER).total_seconds()
            os.utime(path, (retry_at, retry_at))
            return path
        self._write(path, body, now)
        self._failed.pop(symbol, None)
        return path

    def _write(self, path: Path, body: bytes, now: float) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(dir=self._directory, suffix=".part")
        try:
            with os.fdopen(handle, "wb") as temporary:
                temporary.write(body)
            os.utime(name, (now, now))
            os.replace(name, path)
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise
