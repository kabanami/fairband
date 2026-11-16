"""The company logo's fetch against ``httpx.MockTransport`` (never the network) and its file store
in a temporary directory (B-203). The files are synthetic: the PNG signature and made-up bytes."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from fairband.vendors.logos import MAX_BYTES, LogoError, Logos, fetch_logo

URL = "https://images.financialmodelingprep.com/symbol/ACME.png"
PNG = b"\x89PNG\r\n\x1a\n" + b"a synthetic logo"
NEWER = b"\x89PNG\r\n\x1a\n" + b"a newer synthetic logo"
NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


class Host:
    """A host that gives each request the next of its answers and keeps the requests."""

    def __init__(self, *answers: httpx.Response | Exception) -> None:
        self.answers = list(answers)
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _png(body: bytes = PNG) -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": "image/png"})


def test_the_fetch_answers_the_file_and_sends_no_key() -> None:
    host = Host(_png())
    assert fetch_logo(URL, host.transport) == PNG
    (request,) = host.requests
    assert (request.method, str(request.url)) == ("GET", URL)
    assert request.url.query == b""
    assert not {"authorization", "apikey", "cookie"} & set(request.headers)


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(404, text="Symbol Image not found"),
        httpx.Response(500),
        httpx.Response(200, text="Symbol Image not found"),  # a page, not a PNG
        httpx.Response(200, content=b""),
        _png(PNG + b"x" * MAX_BYTES),  # over the size limit
        httpx.ConnectError("no route"),
        httpx.ReadTimeout("slow"),
    ],
)
def test_the_fetch_refuses_what_is_not_a_logo(answer: httpx.Response | Exception) -> None:
    with pytest.raises(LogoError):
        fetch_logo(URL, Host(answer).transport)


def test_the_fetch_follows_no_redirect() -> None:
    """A redirect could lead to any host, so it is a failure, and the fetch asks once."""
    host = Host(httpx.Response(302, headers={"location": "https://example.com/x.png"}), _png())
    with pytest.raises(LogoError):
        fetch_logo(URL, host.transport)
    assert len(host.requests) == 1


def test_a_file_at_the_size_limit_passes() -> None:
    body = PNG + b"x" * (MAX_BYTES - len(PNG))
    assert fetch_logo(URL, Host(_png(body)).transport) == body


class Source:
    """What the store fetches from: each call gives the next of its answers."""

    def __init__(self, *answers: bytes | LogoError) -> None:
        self.answers = list(answers)
        self.asked: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.asked.append(url)
        answer = self.answers.pop(0)
        if isinstance(answer, LogoError):
            raise answer
        return answer


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def _logos(tmp_path: Path, source: Callable[[str], bytes], clock: Clock) -> Logos:
    return Logos(tmp_path / "data" / "logos", source, clock)


def test_the_first_read_fetches_the_file_and_the_next_reads_it(tmp_path: Path) -> None:
    """The file is fetched once and stored under the data folder's ``logos`` by its symbol; a
    later read asks nobody."""
    source, clock = Source(PNG), Clock()
    logos = _logos(tmp_path, source, clock)
    path = logos.file("ACME", URL)
    assert path == tmp_path / "data" / "logos" / "ACME.png"
    assert path.read_bytes() == PNG
    clock.now += timedelta(days=89)
    assert logos.file("ACME", URL) == path
    assert source.asked == [URL]


def test_a_file_older_than_ninety_days_is_fetched_again(tmp_path: Path) -> None:
    source, clock = Source(PNG, NEWER), Clock()
    logos = _logos(tmp_path, source, clock)
    logos.file("ACME", URL)
    clock.now += timedelta(days=90)
    path = logos.file("ACME", URL)
    assert path is not None and path.read_bytes() == NEWER
    clock.now += timedelta(days=89)  # the new file's ninety days start at its fetch
    logos.file("ACME", URL)
    assert source.asked == [URL, URL]


def test_an_old_file_is_kept_when_its_fetch_fails_and_tried_again_a_day_later(
    tmp_path: Path,
) -> None:
    """A failed fetch of an old file leaves it as the answer, and the store asks again a day
    later, not at each read: without the network a read would otherwise wait for a fetch to
    fail every time."""
    source, clock = Source(PNG, LogoError("no route"), NEWER), Clock()
    logos = _logos(tmp_path, source, clock)
    logos.file("ACME", URL)
    clock.now += timedelta(days=90)
    path = logos.file("ACME", URL)
    assert path is not None and path.read_bytes() == PNG
    clock.now += timedelta(hours=23)
    assert logos.file("ACME", URL) == path
    assert source.asked == [URL, URL]
    clock.now += timedelta(hours=1)
    path = logos.file("ACME", URL)
    assert path is not None and path.read_bytes() == NEWER
    assert source.asked == [URL, URL, URL]


def test_a_failed_first_fetch_stores_nothing(tmp_path: Path) -> None:
    """No file and no answer; the next read asks again."""
    source, clock = Source(LogoError("status 404"), PNG), Clock()
    logos = _logos(tmp_path, source, clock)
    assert logos.file("ACME", URL) is None
    directory = tmp_path / "data" / "logos"
    assert not directory.exists() or list(directory.iterdir()) == []
    path = logos.file("ACME", URL)
    assert path is not None and path.read_bytes() == PNG
    assert [p.name for p in directory.iterdir()] == ["ACME.png"]  # no temporary file is left


def test_each_symbol_has_its_own_file(tmp_path: Path) -> None:
    other = "https://images.financialmodelingprep.com/symbol/BF-B.png"
    logos = _logos(tmp_path, Source(PNG, NEWER), Clock())
    first, second = logos.file("ACME", URL), logos.file("BF.B", other)
    assert first is not None and second is not None
    assert (first.name, second.name) == ("ACME.png", "BF.B.png")
    assert (first.read_bytes(), second.read_bytes()) == (PNG, NEWER)
