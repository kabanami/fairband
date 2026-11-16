"""The company logo's read (B-203): ``GET /api/companies/{symbol}/logo`` answers the stored
profile's logo from the data folder's ``logos``, fetched at the first request, and the detail
read names the route where the company has a logo. The fetch is a double that counts its calls;
the file is synthetic, the PNG signature and made-up bytes."""

from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from support.payloads import store_payloads
from support.web import CREATED, HOST, NOW, _settings

from fairband import __main__ as cli
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.vendors.logos import LogoError
from fairband.web.app import create_app

PNG = b"\x89PNG\r\n\x1a\n" + b"a synthetic logo"
URL = "https://images.financialmodelingprep.com/symbol/AAPL.png"


class Source:
    """The fetch's double: the file for every address, or a failure, and the addresses asked."""

    def __init__(self) -> None:
        self.asked: list[str] = []
        self.fails = False

    def __call__(self, url: str) -> bytes:
        self.asked.append(url)
        if self.fails:
            raise LogoError("status 404")
        return PNG


def _profile(image: Any, default: bool = False) -> dict[str, Any]:
    return {"profile": [{"country": "US", "image": image, "defaultImage": default}]}


@pytest.fixture(autouse=True)
def stored(db_path: Path) -> None:
    """AAPL's stored profile has a logo, HGCO's has FMP's placeholder, and AAL has no profile."""
    with closing(connect(db_path)) as conn:
        store_payloads(conn, "AAPL", _profile(URL), CREATED)
        placeholder = "https://images.financialmodelingprep.com/symbol/HGCO.png"
        store_payloads(conn, "HGCO", _profile(placeholder, default=True), CREATED)


@pytest.fixture
def source() -> Source:
    return Source()


@pytest.fixture
def served(tmp_path: Path, db_path: Path, policy: Policy, source: Source) -> Iterator[TestClient]:
    """A client of an app that fetches a logo from ``source``."""
    app = create_app(
        _settings(tmp_path, db_path),
        policy,
        lambda: connect(db_path),
        clock=lambda: NOW,
        fetch_logo=source,
    )
    client = TestClient(app, base_url=HOST)
    yield client
    client.close()


def test_the_logo_is_fetched_once_and_then_read_from_the_data_folder(
    served: TestClient, source: Source, db_path: Path
) -> None:
    """The request carries no ``X-Fairband-Request`` header: an ``<img>`` cannot send one."""
    first = served.get("/api/companies/AAPL/logo")
    assert first.status_code == 200, first.text
    assert first.content == PNG
    assert first.headers["content-type"] == "image/png"
    assert (db_path.parent / "logos" / "AAPL.png").read_bytes() == PNG
    again = served.get("/api/companies/aapl/logo")  # a symbol in any case
    assert (again.status_code, again.content) == (200, PNG)
    assert source.asked == [URL]


def test_the_answer_is_an_image_the_browser_keeps_a_day_and_does_not_sniff(
    served: TestClient,
) -> None:
    headers = served.get("/api/companies/AAPL/logo").headers
    assert headers["cache-control"] == "private, max-age=86400"
    assert headers["x-content-type-options"] == "nosniff"


def test_another_sites_image_tag_is_refused_before_anything_is_fetched(
    served: TestClient, source: Source
) -> None:
    """The read asks for no ``X-Fairband-Request`` header, so it reads what the browser says of
    the request instead: ``Sec-Fetch-Site`` is ``cross-site`` for an image tag on another site
    and ``same-site`` for one on another port of this host, and each is a 403 that fetches
    nothing. The page's own image is ``same-origin``, an address typed in the browser ``none``,
    and a client that is no browser sends no such header."""
    for site in ("cross-site", "same-site"):
        response = served.get("/api/companies/AAPL/logo", headers={"Sec-Fetch-Site": site})
        assert response.status_code == 403, site
        assert response.json() == {"detail": "the logo is read from Fairband's own page"}
    assert source.asked == []
    for site in ("same-origin", "none"):
        response = served.get("/api/companies/AAPL/logo", headers={"Sec-Fetch-Site": site})
        assert response.status_code == 200, site


def test_no_logo_is_a_404_and_asks_nobody(served: TestClient, source: Source) -> None:
    """FMP's placeholder, a company with no stored profile and a symbol nobody stored."""
    for symbol in ("HGCO", "AAL", "NOPE"):
        response = served.get(f"/api/companies/{symbol}/logo")
        assert response.status_code == 404, symbol
        assert response.json() == {"detail": f"no logo for {symbol}"}
    assert source.asked == []


def test_an_address_on_another_host_is_never_fetched(
    served: TestClient, source: Source, db_path: Path
) -> None:
    with closing(connect(db_path)) as conn:
        store_payloads(conn, "AAPL", _profile("https://example.com/symbol/AAPL.png"), NOW)
    assert served.get("/api/companies/AAPL/logo").status_code == 404
    assert source.asked == []


def test_a_failed_fetch_is_a_404_and_the_next_request_asks_again(
    served: TestClient, source: Source, db_path: Path
) -> None:
    source.fails = True
    assert served.get("/api/companies/AAPL/logo").status_code == 404
    assert not (db_path.parent / "logos" / "AAPL.png").exists()
    source.fails = False
    assert served.get("/api/companies/AAPL/logo").content == PNG
    assert source.asked == [URL, URL]


def test_a_name_that_is_no_symbol_is_a_400(served: TestClient, source: Source) -> None:
    response = served.get("/api/companies/AAPL$/logo")
    assert response.status_code == 400
    assert response.json() == {"detail": "'AAPL$' is not a symbol"}
    assert source.asked == []


def test_an_app_given_no_fetch_reads_a_stored_file_and_fetches_none(
    client: TestClient, db_path: Path
) -> None:
    """``create_app`` without a fetch, as every other test builds it, never calls FMP."""
    assert client.get("/api/companies/AAPL/logo").status_code == 404
    logos = db_path.parent / "logos"
    logos.mkdir()
    (logos / "AAPL.png").write_bytes(PNG)
    assert client.get("/api/companies/AAPL/logo").content == PNG


def test_the_detail_read_names_the_logo_route_where_the_company_has_a_logo(
    served: TestClient, source: Source
) -> None:
    """``logo`` is the address the page's ``<img>`` reads; ``None`` for FMP's placeholder and
    without a stored profile, so the page asks for no file. The detail read fetches nothing."""
    assert served.get("/api/companies/AAPL").json()["logo"] == "/api/companies/AAPL/logo"
    assert served.get("/api/companies/HGCO").json()["logo"] is None
    assert served.get("/api/companies/AAL").json()["logo"] is None
    assert source.asked == []


def test_serve_hands_the_app_the_logo_fetch_with_no_fmp_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, source: Source
) -> None:
    """``serve`` passes the app ``fetch_logo`` whether or not it holds an FMP key: FMP's image
    host takes none. The server's data folder is the fixture's, where AAPL's profile is stored."""
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)
    monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)
    answers: list[httpx.Response] = []

    def run_app(app: Any, **kwargs: Any) -> None:
        with TestClient(app, base_url=HOST) as client:
            answers.append(client.get("/api/companies/AAPL/logo"))

    monkeypatch.setattr(cli, "fetch_logo", source)
    monkeypatch.setattr(uvicorn, "run", run_app)
    assert cli.main(["serve"]) == 0
    (answer,) = answers
    assert (answer.status_code, answer.content) == (200, PNG)
    assert source.asked == [URL]
    assert (tmp_path / "data" / "logos" / "AAPL.png").read_bytes() == PNG
