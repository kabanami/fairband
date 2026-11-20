"""The vendor pass-through routes through the app, with a ``Passthrough`` over FMP on a mock
transport that serves the fixtures (``support.vendor``), and the ``serve`` command that builds it
beside the worker on one limiter. The keys are fake."""

import json
import logging
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from support.pe_history import closes_payload, unit_quarters
from support.vendor import FIXTURES, GF_TOKEN, KEY, Vendor
from support.web import HEADER, HOST, NOW

from fairband import __main__ as cli
from fairband.config import Keys
from fairband.policy import Policy
from fairband.refresh import passthrough as passthrough_module
from fairband.refresh.passthrough import Passthrough
from fairband.store.db import connect
from fairband.store.settings import write_settings
from fairband.vendors.fmp import Fmp
from fairband.vendors.limiter import RateLimiter

Q3 = {"year": "2026", "quarter": "3"}


def _fixture(name: str, fixtures: Path = FIXTURES) -> Any:
    return json.loads((fixtures / name).read_text())


def test_no_passthrough_is_503(client: TestClient) -> None:
    response = client.get("/api/vendor/transcript/ACME", params=Q3, headers=HEADER)
    assert (response.status_code, response.json()) == (503, {"detail": "no FMP key"})


@pytest.mark.parametrize(
    "url",
    [
        "/api/vendor/transcript/ACME?year=2026&quarter=3",
        "/api/vendor/filings/ACME",  # refused before the kind is read
        "/api/companies/ACME/multiples-history",
    ],
)
def test_a_read_that_may_call_a_vendor_needs_the_request_header(
    with_passthrough: TestClient, vendor: Vendor, url: str
) -> None:
    """D11 and B-109: a read that may call a vendor spends its quota and stores its answer, and an
    image tag on any other site passes the host check, so the read carries
    ``X-Fairband-Request: 1`` as a write does, else 403 with the writes' sentence and no vendor
    called. The other reads need none."""
    bare = TestClient(with_passthrough.app, base_url=HOST)
    for method in (bare.get, bare.head):
        refused = method(url)
        assert refused.status_code == 403, method
    assert bare.get(url).json() == {"detail": "missing X-Fairband-Request header"}
    assert bare.get(url, headers={"X-Fairband-Request": "0"}).status_code == 403
    assert vendor.paths == []
    assert with_passthrough.get(url).status_code in (200, 400)  # with it: served, or the kind's 400
    for read in ("/api/screen", "/api/companies/AAPL", "/api/companies/AAPL/band-history"):
        assert bare.get(read).status_code == 200, read  # a read of the store alone needs none


@pytest.mark.parametrize("kind", ["filings", "pe-history"])
def test_an_unknown_kind_is_400(
    with_passthrough: TestClient, client: TestClient, vendor: Vendor, kind: str
) -> None:
    """A filing kind, and the P/E history, whose answers the multiples history read alone asks
    since GuruFocus's series went (spec 2026-11-19 6.3), are no kinds of the route."""
    detail = (
        f"unknown vendor kind: {kind} (transcript, news, segments, insider-trades,"
        " transcript-dates or dcf)"
    )
    for app_client in (with_passthrough, client):  # with a key or without
        response = app_client.get(f"/api/vendor/{kind}/ACME", headers=HEADER)
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
    assert (product["newestYear"], geographic["newestYear"]) == (2025, 2025)
    news = with_passthrough.get("/api/vendor/news/ACME", params={"limit": "5"}).json()
    assert "newestYear" not in news
    assert (news["responseId"], news["payload"]) == (3, _fixture("news-stock.ACME.json"))
    trades = with_passthrough.get("/api/vendor/insider-trades/ACME").json()
    assert trades["payload"] == _fixture("insider-trading-search.ACME.json")
    assert vendor.paths == [
        "/stable/revenue-product-segmentation",
        "/stable/revenue-geographic-segmentation",
        "/stable/news/stock",
        "/stable/insider-trading/search",
    ]


def _split(fiscal_year: Any) -> dict[str, Any]:
    """A row of FMP's revenue split with ``fiscal_year`` as its ``fiscalYear``."""
    return {"symbol": "ACME", "fiscalYear": fiscal_year, "period": "FY", "data": {"A": 1}}


@pytest.mark.parametrize(
    ("product", "geographic", "newest"),
    [
        pytest.param(
            [_split(2024), _split(2025), _split(2023)],
            [_split(2023), _split(2021), _split(2022)],
            (2025, 2023),
            id="the-region-split-ends-early",
        ),
        pytest.param([], [_split(2023)], (None, 2023), id="an-empty-list"),
        pytest.param(
            [_split("2026"), _split(2026.5), _split(True), _split(None), {"data": {}}, "x", 7],
            [_split(2022), _split("2025")],
            (None, 2022),
            id="rows-without-a-whole-number",
        ),
        pytest.param(
            {"Error Message": "No data"}, [{"fiscalYear": 2020}], (None, 2020), id="not-a-list"
        ),
    ],
)
def test_each_revenue_split_names_its_newest_year(
    with_passthrough: TestClient,
    vendor: Vendor,
    product: Any,
    geographic: Any,
    newest: tuple[int | None, int | None],
) -> None:
    """Spec 2026-11-15 11 (B-118): FMP's revenue by region can end years before its revenue by
    product (QCOM's ended at fiscal 2023), so each part of the ``segments`` answer names
    ``newestYear``, the largest ``fiscalYear`` among its payload's rows that hold a whole number
    there, null where none does or the payload is not a list; the payload stays whole."""
    bodies = {
        "/stable/revenue-product-segmentation": product,
        "/stable/revenue-geographic-segmentation": geographic,
    }
    vendor.answer = lambda request: httpx.Response(200, json=bodies[request.url.path])
    answer = with_passthrough.get("/api/vendor/segments/ACME").json()
    parts = answer["responses"]
    assert list(parts) == ["product", "geographic"]
    for part, body in (("product", product), ("geographic", geographic)):
        assert list(parts[part]) == ["responseId", "observedAt", "reused", "payload", "newestYear"]
        assert parts[part]["payload"] == body
    assert (parts["product"]["newestYear"], parts["geographic"]["newestYear"]) == newest
    again = with_passthrough.get("/api/vendor/segments/ACME").json()["responses"]
    # A reuse names it too; a payload that is not a list is stored unusable and fetched again
    # (spec 2026-11-17 8.1).
    lists = [isinstance(body, list) for body in (product, geographic)]
    assert [again[part]["reused"] for part in again] == lists
    assert (again["product"]["newestYear"], again["geographic"]["newestYear"]) == newest


def test_dcf_over_the_api(with_passthrough: TestClient, vendor: Vendor) -> None:
    answer = with_passthrough.get("/api/vendor/dcf/ACME").json()
    assert list(answer) == ["responses"]
    dcf, levered = answer["responses"]["dcf"], answer["responses"]["levered"]
    for part in (dcf, levered):  # the whole response, no newest year: not a revenue split
        assert list(part) == ["responseId", "observedAt", "reused", "payload"]
    assert (dcf["responseId"], levered["responseId"]) == (1, 2)
    assert dcf["payload"] == _fixture("discounted-cash-flow.ACME.json")
    assert levered["payload"] == _fixture("levered-discounted-cash-flow.ACME.json")
    assert vendor.paths == ["/stable/discounted-cash-flow", "/stable/levered-discounted-cash-flow"]


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


def test_insider_trades_answer_the_newest_trades_up_to_a_limit(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    """FMP's page, up to 100 trades with the newest first, is stored whole. ``limit`` cuts the
    answer to the first of them, so a ``response:`` ref names a trade by the same place in the
    stored page, and ``tradeCount`` says how many the stored page holds."""
    trade = _fixture("insider-trading-search.ACME.json")[0]
    names = ["Roe Jane", "Doe John", "Poe Ann"]
    page = [trade | {"reportingName": name} for name in names]
    vendor.answer = lambda request: httpx.Response(200, json=page)
    url = "/api/vendor/insider-trades/ACME"
    for bad in ("0", "101"):  # refused before any call: FMP is not asked
        refused = with_passthrough.get(url, params={"limit": bad})
        assert (refused.status_code, refused.json()["detail"]) == (400, "limit is 1 to 100")
    assert vendor.paths == []
    cut = with_passthrough.get(url, params={"limit": "2"}).json()
    assert [t["reportingName"] for t in cut["payload"]] == ["Roe Jane", "Doe John"]
    assert (cut["tradeCount"], cut["reused"]) == (3, False)
    whole = with_passthrough.get(url).json()
    assert [t["reportingName"] for t in whole["payload"]] == names
    assert (whole["tradeCount"], whole["reused"], whole["responseId"]) == (3, True, 1)
    assert vendor.paths == ["/stable/insider-trading/search"]


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


def test_serve_builds_the_pass_through_on_fmp_alone_and_closes_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, vendor: Vendor
) -> None:
    """With a GuruFocus key too, ``serve`` builds the pass-through over FMP alone (spec 2026-11-19
    6.3): the multiples read builds the trailing series from FMP's closes and quarters, with no key
    in its answer and no GuruFocus call, and the pass-through's FMP client closes when the server
    stops."""
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FAIRBAND_FMP_KEY", KEY)
    monkeypatch.setenv("FAIRBAND_GURUFOCUS_KEY", GF_TOKEN)
    closed: list[str] = []
    build_fmp = cli.build_fmp

    def passthrough_fmp(keys: Keys, policy: Policy, *, limiter: RateLimiter | None = None) -> Fmp:
        client = build_fmp(keys, policy, transport=vendor.transport, limiter=limiter)
        close = client.close
        monkeypatch.setattr(client, "close", lambda: (closed.append("fmp"), close()))
        return client

    answers = {  # a trailing EPS of 1.00: the P/E is the close
        "/stable/historical-price-eod/full": closes_payload("ACME", {"2026-10-30": 40.0}),
        "/stable/income-statement": unit_quarters("ACME"),
    }
    vendor.answer = lambda request: httpx.Response(200, json=answers[request.url.path])
    history: list[httpx.Response] = []

    def run_app(app: Any, **kwargs: Any) -> None:
        with TestClient(app, base_url=HOST, headers=HEADER) as client:
            history.append(client.get("/api/companies/ACME/multiples-history"))
        assert closed == []  # still serving

    monkeypatch.setattr(cli, "build_fmp", passthrough_fmp)
    monkeypatch.setattr(uvicorn, "run", run_app)
    assert cli.main(["serve"]) == 0
    [answer] = history
    assert answer.status_code == 200 and answer.json()["peNote"] is None
    points = [(point["day"], point["value"]) for point in answer.json()["pe"]["points"]]
    assert points == [("2026-10-30", 40.0)]
    assert vendor.paths == ["/stable/historical-price-eod/full", "/stable/income-statement"]
    assert KEY not in answer.text and GF_TOKEN not in answer.text
    assert closed == ["fmp"]
