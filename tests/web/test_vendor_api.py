"""The vendor pass-through routes through the app, with a ``Passthrough`` over FMP, and GuruFocus
where a test gives it one, on a mock transport that serves the fixtures, and the ``serve`` command
that builds it beside the worker on one limiter. The keys are fake."""

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
from fairband.refresh import passthrough as passthrough_module
from fairband.refresh.passthrough import Passthrough
from fairband.store.db import connect
from fairband.store.settings import write_settings
from fairband.vendors import fmp as fmp_api
from fairband.vendors import gurufocus as gurufocus_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.http import VendorHttp
from fairband.vendors.limiter import RateLimiter
from fairband.web.app import create_app

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fmp"
GF_FIXTURES = FIXTURES.parent / "gurufocus"
KEY = "fake-fmp-key-0003"  # not a real key
GF_TOKEN = "fakegfhalf3:fakegfhalf4"  # not a real token
Q3 = {"year": "2026", "quarter": "3"}
NO_GF_KEY = "no GuruFocus key: the pe-history pass-through is off"


def _fixture(name: str, fixtures: Path = FIXTURES) -> Any:
    return json.loads((fixtures / name).read_text())


class Vendor:
    """FMP and GuruFocus on a mock transport: an FMP request reads ``fmp/<route>.<symbol>.json``
    (a slash in the route becomes a dash; news names its symbol in ``symbols``), a GuruFocus one
    ``gurufocus/<route>.<symbol>.json``, 404 without one; ``answer``, when set, makes each
    response instead. ``paths`` keeps each request's path, a GuruFocus token in it replaced by
    ``<token>``."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        self.answer: Any = None  # a function of the request to its response
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path.replace(GF_TOKEN, "<token>"))
        if self.answer is not None:
            response: httpx.Response = self.answer(request)
            return response
        if request.url.host == "api.gurufocus.com":
            *_, symbol, route = request.url.path.split("/")
            fixture = GF_FIXTURES / f"{route}.{symbol}.json"
        else:
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
def fmp(policy: Policy, vendor: Vendor) -> Iterator[Fmp]:
    with VendorHttp(
        fmp_api.BASE_URL,
        [KEY],
        policy.refresh,
        transport=vendor.transport,
        sleep=lambda _: None,
        clock=lambda: NOW,
    ) as http:
        yield Fmp(http, KEY)


@pytest.fixture
def passthrough(db_path: Path, policy: Policy, fmp: Fmp) -> Passthrough:
    return Passthrough(fmp, lambda: connect(db_path), policy, lambda: NOW, (KEY,))


@pytest.fixture
def gurufocus(policy: Policy, vendor: Vendor) -> Iterator[GuruFocus]:
    with VendorHttp(
        gurufocus_api.BASE_URL,
        [GF_TOKEN],
        policy.refresh,
        transport=vendor.transport,
        sleep=lambda _: None,
        clock=lambda: NOW,
    ) as http:
        yield GuruFocus(http, GF_TOKEN)


def _client(tmp_path: Path, db_path: Path, policy: Policy, passthrough: Passthrough) -> TestClient:
    def conn_factory() -> Any:
        return connect(db_path)

    settings = _settings(tmp_path, db_path)
    app = create_app(settings, policy, conn_factory, clock=lambda: NOW, passthrough=passthrough)
    return TestClient(app, base_url=HOST, headers=HEADER)  # a read that may call a vendor (D11)


@pytest.fixture
def with_passthrough(
    tmp_path: Path, db_path: Path, policy: Policy, passthrough: Passthrough
) -> Iterator[TestClient]:
    """A pass-through over FMP alone: no GuruFocus key."""
    with _client(tmp_path, db_path, policy, passthrough) as client:
        yield client


@pytest.fixture
def with_gurufocus(
    tmp_path: Path, db_path: Path, policy: Policy, fmp: Fmp, gurufocus: GuruFocus
) -> Iterator[TestClient]:
    """A pass-through over FMP and GuruFocus."""
    secrets = (KEY, GF_TOKEN)
    both = Passthrough(fmp, lambda: connect(db_path), policy, lambda: NOW, secrets, gurufocus)
    with _client(tmp_path, db_path, policy, both) as client:
        yield client


def test_no_passthrough_is_503(client: TestClient) -> None:
    response = client.get("/api/vendor/transcript/ACME", params=Q3, headers=HEADER)
    assert (response.status_code, response.json()) == (503, {"detail": "no FMP key"})


@pytest.mark.parametrize(
    "url",
    [
        "/api/vendor/transcript/ACME?year=2026&quarter=3",
        "/api/vendor/pe-history/ACME",
        "/api/vendor/filings/ACME",  # refused before the kind is read
        "/api/companies/ACME/multiples-history",
    ],
)
def test_a_read_that_may_call_a_vendor_needs_the_request_header(
    with_gurufocus: TestClient, vendor: Vendor, url: str
) -> None:
    """D11 and B-109: a read that may call a vendor spends its quota and stores its answer, and an
    image tag on any other site passes the host check, so the read carries
    ``X-Fairband-Request: 1`` as a write does, else 403 with the writes' sentence and no vendor
    called. The other reads need none."""
    bare = TestClient(with_gurufocus.app, base_url=HOST)
    for method in (bare.get, bare.head):
        refused = method(url)
        assert refused.status_code == 403, method
    assert bare.get(url).json() == {"detail": "missing X-Fairband-Request header"}
    assert bare.get(url, headers={"X-Fairband-Request": "0"}).status_code == 403
    assert vendor.paths == []
    assert with_gurufocus.get(url).status_code in (200, 400)  # with it: served, or the kind's 400
    for read in ("/api/screen", "/api/companies/AAPL", "/api/companies/AAPL/band-history"):
        assert bare.get(read).status_code == 200, read  # a read of the store alone needs none


def test_an_unknown_kind_is_400(
    with_passthrough: TestClient, client: TestClient, vendor: Vendor
) -> None:
    detail = (
        "unknown vendor kind: filings (transcript, news, segments, insider-trades,"
        " transcript-dates, dcf or pe-history)"
    )
    for app_client in (with_passthrough, client):  # with a key or without
        response = app_client.get("/api/vendor/filings/ACME", headers=HEADER)
        assert (response.status_code, response.json()) == (400, {"detail": detail})
    assert vendor.paths == []


@pytest.mark.parametrize(
    ("path", "params", "detail"),
    [
        ("transcript/ACME", {"year": "2026"}, "a transcript needs year and quarter"),
        ("transcript/ACME", {"year": "2026", "quarter": "5"}, "quarter must be 1 to 4"),
        ("transcript/ACME", {"year": "2026", "quarter": "Q3"}, "quarter: "),
        ("news/ACME", {"limit": "0"}, "limit is 1 to 100"),
        ("news/ACME", {"limit": "101"}, "limit is 1 to 100"),
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


def test_dcf_over_the_api(with_passthrough: TestClient, vendor: Vendor) -> None:
    answer = with_passthrough.get("/api/vendor/dcf/ACME").json()
    assert list(answer) == ["responses"]
    dcf, levered = answer["responses"]["dcf"], answer["responses"]["levered"]
    assert (dcf["responseId"], levered["responseId"]) == (1, 2)
    assert dcf["payload"] == _fixture("discounted-cash-flow.ACME.json")
    assert levered["payload"] == _fixture("levered-discounted-cash-flow.ACME.json")
    assert vendor.paths == ["/stable/discounted-cash-flow", "/stable/levered-discounted-cash-flow"]


def test_pe_history_over_the_api(with_gurufocus: TestClient, vendor: Vendor) -> None:
    first = with_gurufocus.get("/api/vendor/pe-history/acme")
    second = with_gurufocus.get("/api/vendor/pe-history/ACME")
    assert first.status_code == second.status_code == 200
    payload = _fixture("pettm.ACME.json", GF_FIXTURES)
    answer = {"responseId": 1, "observedAt": NOW.isoformat(), "reused": False, "payload": payload}
    assert first.json() == answer and second.json() == {**answer, "reused": True}
    assert vendor.paths == ["/public/user/<token>/stock/ACME/pettm"]
    assert GF_TOKEN not in first.text


def test_pe_history_without_a_gurufocus_key_is_503(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    response = with_passthrough.get("/api/vendor/pe-history/ACME")
    assert (response.status_code, response.json()) == (503, {"detail": NO_GF_KEY})
    assert vendor.paths == []


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


def test_busy_pass_throughs_are_503(
    with_passthrough: TestClient,
    passthrough: Passthrough,
    vendor: Vendor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Four transcript calls held at the vendor take every slot: a request whose call waits past
    the bound (shortened here) answers 503 with the sentence; a reuse still answers 200."""
    monkeypatch.setattr(passthrough_module, "PASSTHROUGH_WAIT_S", 0.2)
    assert with_passthrough.get("/api/vendor/news/ACME").status_code == 200  # stored
    entered, release = threading.Semaphore(0), threading.Event()

    def held(request: httpx.Request) -> httpx.Response:
        entered.release()
        release.wait(5)
        return httpx.Response(200, json=[])

    vendor.answer = held
    quarters = [{"year": "2026", "quarter": q} for q in "1234"]
    threads = [
        threading.Thread(target=passthrough.fetch, args=("transcript", "ACME", params))
        for params in quarters
    ]
    try:
        for thread in threads:
            thread.start()
        for _ in threads:
            assert entered.acquire(timeout=5)
        busy = with_passthrough.get("/api/vendor/transcript/ACME", params=Q3)
        reused = with_passthrough.get("/api/vendor/news/ACME")
    finally:
        release.set()
        for thread in threads:
            thread.join(5)
    assert (busy.status_code, busy.json()) == (
        503,
        {"detail": "the pass-throughs are busy: four calls are in flight, try again"},
    )
    assert reused.status_code == 200 and reused.json()["reused"] is True
    assert vendor.paths.count("/stable/earning-call-transcript") == 4


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
        with TestClient(app, base_url=HOST, headers=HEADER) as client:
            answers.append(client.get("/api/vendor/transcript/ACME", params=Q3))
            limiter = limiters["passthrough"]
            assert limiter is not None
            paces.append(limiter.calls_per_minute)
            with closing(connect(tmp_path / "data" / "fairband.db")) as conn:
                write_settings(conn, {"refresh.fmp_calls_per_minute": 600}, None, NOW)
            answers.append(client.post("/api/refresh", json={"kind": "full"}))
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


def test_serve_hands_the_pass_through_a_gurufocus_client_and_closes_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, vendor: Vendor
) -> None:
    """With a GuruFocus key, ``serve`` builds the pass-through's GuruFocus client, its token
    among the secrets: the pe-history route and the multiples read answer through it, with no
    token in either, and the client closes when the server stops."""
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FAIRBAND_FMP_KEY", KEY)
    monkeypatch.setenv("FAIRBAND_GURUFOCUS_KEY", GF_TOKEN)
    closed: list[str] = []
    build_fmp, build_gurufocus = cli.build_fmp, cli.build_gurufocus

    def passthrough_fmp(keys: Keys, policy: Policy, *, limiter: RateLimiter | None = None) -> Fmp:
        return build_fmp(keys, policy, transport=vendor.transport, limiter=limiter)

    def passthrough_gurufocus(keys: Keys, policy: Policy) -> GuruFocus | None:
        client = build_gurufocus(keys, policy, transport=vendor.transport)
        assert client is not None
        close = client.close
        monkeypatch.setattr(client, "close", lambda: (closed.append("gurufocus"), close()))
        return client

    answers: list[httpx.Response] = []

    def run_app(app: Any, **kwargs: Any) -> None:
        with TestClient(app, base_url=HOST, headers=HEADER) as client:
            answers.append(client.get("/api/vendor/pe-history/ACME"))
            answers.append(client.get("/api/companies/ACME/multiples-history"))
        assert closed == []  # still serving

    monkeypatch.setattr(cli, "build_fmp", passthrough_fmp)
    monkeypatch.setattr(cli, "build_gurufocus", passthrough_gurufocus)
    monkeypatch.setattr(uvicorn, "run", run_app)
    assert cli.main(["serve"]) == 0
    fetched, history = answers
    assert fetched.status_code == history.status_code == 200
    assert fetched.json()["payload"] == _fixture("pettm.ACME.json", GF_FIXTURES)
    assert history.json()["pe"]["responseId"] == fetched.json()["responseId"]  # reused
    assert GF_TOKEN not in fetched.text + history.text
    assert vendor.paths == ["/public/user/<token>/stock/ACME/pettm"]
    assert closed == ["gurufocus"]


def test_serve_without_a_gurufocus_key_builds_no_gurufocus_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FAIRBAND_FMP_KEY", KEY)
    monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)
    answers: list[httpx.Response] = []

    def run_app(app: Any, **kwargs: Any) -> None:
        with TestClient(app, base_url=HOST, headers=HEADER) as client:
            answers.append(client.get("/api/vendor/pe-history/ACME"))

    monkeypatch.setattr(uvicorn, "run", run_app)
    assert cli.main(["serve"]) == 0
    [answer] = answers
    assert (answer.status_code, answer.json()) == (503, {"detail": NO_GF_KEY})
