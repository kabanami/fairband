"""The vendor pass-through routes through the app, with a ``Passthrough`` over FMP on a mock
transport that serves the FMP fixtures, and the ``serve`` command that builds it beside the
worker on one limiter. The key is fake."""

import json
import logging
import threading
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from support.web import HEADER, HOST, NOW, _settings

from fairband import __main__ as cli
from fairband.config import Keys
from fairband.policy import Policy
from fairband.refresh.passthrough import Passthrough
from fairband.store.db import connect
from fairband.store.settings import write_settings
from fairband.vendors import fmp as fmp_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorHttp
from fairband.vendors.limiter import RateLimiter
from fairband.web.app import create_app

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fmp"
KEY = "fake-fmp-key-0003"  # not a real key
Q3 = {"year": "2026", "quarter": "3"}


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class Vendor:
    """FMP on a mock transport: a request reads ``fmp/<route>.<symbol>.json`` (a slash in the
    route becomes a dash; news names its symbol in ``symbols``), 404 without one; ``answer``,
    when set, makes each response instead. ``paths`` keeps each request's path."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        self.answer: Any = None  # a function of the request to its response
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        if self.answer is not None:
            response: httpx.Response = self.answer(request)
            return response
        route = request.url.path.removeprefix("/stable/").replace("/", "-")
        params = request.url.params
        fixture = FIXTURES / f"{route}.{params.get('symbol') or params.get('symbols')}.json"
        if not fixture.is_file():
            return httpx.Response(404, json={"Error Message": "no fixture"})
        return httpx.Response(
            200, content=fixture.read_bytes(), headers={"Content-Type": "application/json"}
        )


@pytest.fixture
def vendor() -> Vendor:
    return Vendor()


@pytest.fixture
def with_passthrough(
    tmp_path: Path, db_path: Path, policy: Policy, vendor: Vendor
) -> Iterator[TestClient]:
    with VendorHttp(
        fmp_api.BASE_URL,
        [KEY],
        policy.refresh,
        transport=vendor.transport,
        sleep=lambda _: None,
        clock=lambda: NOW,
    ) as http:

        def conn_factory() -> Any:
            return connect(db_path)

        passthrough = Passthrough(Fmp(http, KEY), conn_factory, policy, lambda: NOW, (KEY,))
        settings = _settings(tmp_path, db_path)
        app = create_app(settings, policy, conn_factory, clock=lambda: NOW, passthrough=passthrough)
        with TestClient(app, base_url=HOST) as client:
            yield client


def test_no_passthrough_is_503(client: TestClient) -> None:
    response = client.get("/api/vendor/transcript/ACME", params=Q3)
    assert (response.status_code, response.json()) == (503, {"detail": "no FMP key"})


def test_an_unknown_kind_is_400(
    with_passthrough: TestClient, client: TestClient, vendor: Vendor
) -> None:
    detail = "unknown vendor kind: filings (transcript, news, segments or insider-trades)"
    for app_client in (with_passthrough, client):  # with a key or without
        response = app_client.get("/api/vendor/filings/ACME")
        assert (response.status_code, response.json()) == (400, {"detail": detail})
    assert vendor.paths == []


@pytest.mark.parametrize(
    ("path", "params", "detail"),
    [
        ("transcript/ACME", {"year": "2026"}, "a transcript needs year and quarter"),
        ("transcript/ACME", {"year": "2026", "quarter": "5"}, "quarter must be 1 to 4"),
        ("transcript/ACME", {"year": "2026", "quarter": "Q3"}, "quarter: "),
        ("news/ACME", {"limit": "0"}, "limit must be at least 1"),
        ("news/A$B", {}, "'A$B' is not a symbol"),
    ],
)
def test_a_bad_parameter_is_400(
    with_passthrough: TestClient, vendor: Vendor, path: str, params: dict[str, str], detail: str
) -> None:
    response = with_passthrough.get(f"/api/vendor/{path}", params=params)
    assert response.status_code == 400 and response.json()["detail"].startswith(detail)
    assert vendor.paths == []


def test_a_transcript_over_the_api(with_passthrough: TestClient, vendor: Vendor) -> None:
    first = with_passthrough.get("/api/vendor/transcript/acme", params=Q3)
    second = with_passthrough.get("/api/vendor/transcript/ACME", params=Q3)
    assert first.status_code == second.status_code == 200
    payload = _fixture("earning-call-transcript.ACME.json")
    answer = {"responseId": 1, "observedAt": NOW.isoformat(), "reused": False, "payload": payload}
    assert first.json() == answer
    assert second.json() == {**answer, "reused": True}
    assert vendor.paths == ["/stable/earning-call-transcript"]


def test_segments_news_and_insider_trades_over_the_api(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    segments = with_passthrough.get("/api/vendor/segments/ACME").json()
    assert list(segments) == ["responses"]
    product, geographic = segments["responses"]["product"], segments["responses"]["geographic"]
    assert (product["responseId"], geographic["responseId"]) == (1, 2)
    assert product["payload"] == _fixture("revenue-product-segmentation.ACME.json")
    assert geographic["payload"] == _fixture("revenue-geographic-segmentation.ACME.json")
    news = with_passthrough.get("/api/vendor/news/ACME", params={"limit": "5"}).json()
    assert (news["responseId"], news["payload"]) == (3, _fixture("news-stock.ACME.json"))
    trades = with_passthrough.get("/api/vendor/insider-trades/ACME").json()
    assert trades["payload"] == _fixture("insider-trading-search.ACME.json")
    assert vendor.paths == [
        "/stable/revenue-product-segmentation",
        "/stable/revenue-geographic-segmentation",
        "/stable/news/stock",
        "/stable/insider-trading/search",
    ]


def test_no_key_in_the_answer(
    with_passthrough: TestClient,
    vendor: Vendor,
    db_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A vendor that echoes the request's URL, key and all, in its body; then one that refuses
    with the key in its sentence. Neither the answers, the store nor the log hold the key."""
    vendor.answer = lambda request: httpx.Response(200, json=[{"asked": str(request.url)}])
    with caplog.at_level(logging.INFO):
        answer = with_passthrough.get("/api/vendor/news/ACME")
        vendor.answer = lambda request: httpx.Response(
            403, json={"Error Message": f"Invalid API KEY: {KEY}"}
        )
        refused = with_passthrough.get("/api/vendor/transcript/ACME", params=Q3)
    assert answer.status_code == 200 and KEY not in answer.text
    asked = "https://financialmodelingprep.com/stable/news/stock?symbols=ACME&limit=20&apikey=<key>"
    assert answer.json()["payload"] == [{"asked": asked}]
    assert refused.status_code == 502 and KEY not in refused.text
    assert refused.json()["detail"].startswith(
        "GET https://financialmodelingprep.com/stable/earning-call-transcript"
        "?symbol=ACME&year=2026&quarter=3&apikey=<key> -> 403 Forbidden: "
    )
    with closing(connect(db_path)) as conn:
        stored = [tuple(r) for r in conn.execute("SELECT payload, error FROM vendor_responses")]
    assert len(stored) == 2 and all(KEY not in str(row) for row in stored)
    assert "apikey=<key>" in caplog.text and KEY not in caplog.text


def test_a_body_that_is_not_json_is_502(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    vendor.answer = lambda request: httpx.Response(
        200, text="Limit Reach", headers={"Content-Type": "text/plain"}
    )
    response = with_passthrough.get("/api/vendor/insider-trades/ACME")
    assert response.status_code == 502
    assert response.json()["detail"] == (
        "GET https://financialmodelingprep.com/stable/insider-trading/search"
        "?symbol=ACME&page=0&limit=100&apikey=<key> -> 200 with a body that is not JSON"
    )
    with closing(connect(db_path)) as conn:
        [row] = conn.execute("SELECT http_status, payload, error FROM vendor_responses")
    assert tuple(row) == (200, "Limit Reach", "unusable payload: Limit Reach")
    vendor.answer = None
    again = with_passthrough.get("/api/vendor/insider-trades/ACME").json()
    assert (again["responseId"], again["reused"]) == (2, False)


# --- python -m fairband serve ----------------------------------------------------------------


def _join_runs() -> None:
    """Wait for the run and fetch threads: no test leaves one running."""
    for thread in threading.enumerate():
        if thread.name.startswith("fairband-"):
            thread.join(5)
            assert not thread.is_alive(), thread.name


def test_serve_paces_the_runs_and_the_pass_through_on_one_limiter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, vendor: Vendor
) -> None:
    """``serve`` builds one limiter at the pace of the effective policy as it starts and hands it
    to the pass-through's client and to each run's; a run paces it to the policy it runs under,
    so a pace saved since the start is the pass-through's too once a run has started."""
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FAIRBAND_FMP_KEY", KEY)
    monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)
    limiters: dict[str, RateLimiter | None] = {}
    build_clients, build_fmp = cli.build_clients, cli.build_fmp

    def run_clients(keys: Keys, policy: Policy, *, limiter: RateLimiter | None = None) -> Any:
        limiters["run"] = limiter
        return build_clients(keys, policy, transport=vendor.transport, limiter=limiter)

    def passthrough_client(
        keys: Keys, policy: Policy, *, limiter: RateLimiter | None = None
    ) -> Fmp:
        limiters["passthrough"] = limiter
        return build_fmp(keys, policy, transport=vendor.transport, limiter=limiter)

    paces: list[float] = []
    answers: list[httpx.Response] = []

    def run_app(app: Any, **kwargs: Any) -> None:
        with TestClient(app, base_url=HOST) as client:
            answers.append(client.get("/api/vendor/transcript/ACME", params=Q3))
            limiter = limiters["passthrough"]
            assert limiter is not None
            paces.append(limiter.calls_per_minute)
            with closing(connect(tmp_path / "data" / "fairband.db")) as conn:
                write_settings(conn, {"refresh.fmp_calls_per_minute": 600}, None, NOW)
            answers.append(client.post("/api/refresh", json={"kind": "full"}, headers=HEADER))
            _join_runs()
            paces.append(limiter.calls_per_minute)

    monkeypatch.setattr(cli, "build_clients", run_clients)
    monkeypatch.setattr(cli, "build_fmp", passthrough_client)
    monkeypatch.setattr(uvicorn, "run", run_app)
    assert cli.main(["serve"]) == 0
    transcript, started = answers
    assert transcript.status_code == 200 and transcript.json()["reused"] is False
    assert (started.status_code, started.json()) == (200, {"refreshId": 1})
    limiter = limiters["run"]
    assert limiter is not None and limiter is limiters["passthrough"]
    # The pass-through's call and the run's screener call, which found no fixture.
    assert limiter.totals().calls == 2
    assert paces == [2850, 600]
