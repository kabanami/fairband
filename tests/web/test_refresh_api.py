"""The refresh routes and the D11 guards through the app, on a temporary migrated database, with a
``RefreshWorker`` over FMP on a mock transport, and the ``serve`` command that builds them.
``fetch_company`` is replaced by a gate that holds each fetch until the test releases it, so a run
stays in its fetch stage while the test looks."""

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import closing
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from fairband import __main__ as cli
from fairband.config import DEFAULT_PORT, Keys, MissingKey, Settings
from fairband.engine import METHOD_VERSION
from fairband.policy import Policy, load_policy
from fairband.policy.tax import load_tax_table
from fairband.refresh import run as run_module
from fairband.refresh.fetch import FetchOutcome
from fairband.refresh.run import Progress, Refresh
from fairband.refresh.worker import RefreshWorker
from fairband.store.db import connect, migrate
from fairband.store.refreshes import create_refresh, items, latest_refresh
from fairband.vendors import fmp as fmp_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorHttp
from fairband.web.app import create_app

NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
KEY = "fake-fmp-key-0002"  # not a real key
HOST = "http://127.0.0.1:8470"
POST = {"X-Fairband-Request": "1"}
MISSING_HEADER = {"detail": "missing X-Fairband-Request header"}


class Gate:
    """Stands in for ``fetch_company``: each fetch waits for ``release``, then reports its symbol
    fetched with nothing called. ``entered`` is set when the first fetch starts."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def __call__(self, conn: Any, fmp: Any, gf: Any, symbol: str, *rest: Any) -> FetchOutcome:
        self.entered.set()
        self.release.wait(5)
        return FetchOutcome(symbol, 0, 0, (), None)


def join_runs() -> None:
    """Wait for the run and fetch threads: no test leaves one running."""
    for thread in threading.enumerate():
        if thread.name.startswith("fairband-"):
            thread.join(5)
            assert not thread.is_alive(), thread.name


@pytest.fixture
def policy() -> Policy:
    return load_policy()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "data" / "fairband.db"
    with closing(connect(path)) as conn:
        migrate(conn)
    return path


@pytest.fixture
def fmp(policy: Policy) -> Iterator[Fmp]:
    """FMP over a transport that answers the screener with no rows and anything else 404."""

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/company-screener"):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    transport = httpx.MockTransport(answer)
    with VendorHttp(
        fmp_api.BASE_URL, [KEY], policy.refresh, transport=transport, sleep=lambda _: None
    ) as http:
        yield Fmp(http, KEY)


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Iterator[Gate]:
    gate = Gate()
    monkeypatch.setattr(run_module, "fetch_company", gate)
    yield gate
    gate.release.set()
    join_runs()


@pytest.fixture
def worker(db_path: Path, fmp: Fmp, policy: Policy, gate: Gate) -> Iterator[RefreshWorker]:
    tax = load_tax_table()

    def make_refresh(cancel: threading.Event, on_progress: Callable[[Progress], None]) -> Refresh:
        return Refresh(
            lambda: connect(db_path),
            fmp,
            None,
            policy,
            tax,
            lambda: NOW,
            cancel,
            on_progress,
            [KEY],
        )

    worker = RefreshWorker(make_refresh, wait_s=0.1)
    yield worker
    worker.cancel()
    gate.release.set()
    join_runs()


def make_client(
    tmp_path: Path, db_path: Path, policy: Policy, worker: RefreshWorker | None
) -> TestClient:
    settings = Settings(tmp_path / "data", tmp_path / "config", db_path, DEFAULT_PORT)
    app = create_app(settings, policy, lambda: connect(db_path), worker, clock=lambda: NOW)
    return TestClient(app, base_url=HOST)


@pytest.fixture
def client_with_worker(
    tmp_path: Path, db_path: Path, policy: Policy, worker: RefreshWorker
) -> Iterator[TestClient]:
    with make_client(tmp_path, db_path, policy, worker) as client:
        yield client


@pytest.fixture
def client_without_worker(tmp_path: Path, db_path: Path, policy: Policy) -> Iterator[TestClient]:
    with make_client(tmp_path, db_path, policy, None) as client:
        yield client


def start(client: TestClient, **body: Any) -> httpx.Response:
    return client.post("/api/refresh", json=body, headers=POST)


def current(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/refresh/current")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_api_start_status_cancel(client_with_worker: TestClient, gate: Gate, db_path: Path) -> None:
    client = client_with_worker
    response = start(client, kind="scoped", symbols=["ACME", "BOLT"])
    assert (response.status_code, response.json()) == (200, {"refreshId": 1})
    assert gate.entered.wait(5)
    assert current(client) == {
        "refresh": {
            "id": 1,
            "stage": "fetch",
            "done": 0,
            "failed": 0,
            "remaining": 2,
            "current": None,
        }
    }
    with closing(connect(db_path)) as conn:  # the progress is on the record too
        assert [(i.symbol, i.status) for i in items(conn, 1)] == [
            ("ACME", "fetching"),
            ("BOLT", "fetching"),
        ]

    response = client.post("/api/refresh/cancel", headers=POST)
    assert (response.status_code, response.json()) == (200, {"cancelled": True})
    gate.release.set()
    join_runs()  # the fetches in flight finish; the run ends cancelled with no value stage
    assert current(client) == {
        "refresh": None,
        "last": {
            "id": 1,
            "kind": "scoped",
            "status": "cancelled",
            "stage": "fetch",
            "startedAt": "2026-11-01T09:30:00+00:00",
            "finishedAt": "2026-11-01T09:30:00+00:00",
            "message": None,
            "calibration": None,
        },
        "error": None,
    }
    # A cancel with no run alive changes nothing.
    assert client.post("/api/refresh/cancel", headers=POST).json() == {"cancelled": True}


def test_api_refuses_second_refresh(
    client_with_worker: TestClient, gate: Gate, db_path: Path
) -> None:
    client = client_with_worker
    first = start(client, kind="scoped", symbols=["ACME"]).json()["refreshId"]
    assert gate.entered.wait(5)
    response = start(client, kind="full")
    assert (response.status_code, response.json()) == (409, {"running": first})
    gate.release.set()
    join_runs()
    assert current(client)["last"]["status"] == "done"

    # A refresh another process runs (the command) is refused the same way.
    with closing(connect(db_path)) as conn:
        other = create_refresh(conn, "scoped", ["BOLT"], "fairband-policy-v1", METHOD_VERSION, NOW)
    response = start(client, kind="scoped", symbols=["ACME"])
    assert (response.status_code, response.json()) == (409, {"running": other})


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"kind": "weekly"}, "unknown refresh kind: weekly"),
        ({"kind": "scoped"}, "a scoped refresh needs symbols"),
        ({"kind": "scoped", "symbols": []}, "a scoped refresh needs symbols"),
        ({"kind": "price"}, "the price refresh is built in a later task"),
        ({"kind": "full", "symbols": ["ACME"]}, "a full refresh takes no symbols"),
    ],
)
def test_api_refresh_bad_request_400(
    client_with_worker: TestClient, db_path: Path, body: dict[str, Any], detail: str
) -> None:
    response = client_with_worker.post("/api/refresh", json=body, headers=POST)
    assert (response.status_code, response.json()) == (400, {"detail": detail})
    with closing(connect(db_path)) as conn:
        assert latest_refresh(conn) is None


def test_api_reports_the_last_error(client_with_worker: TestClient) -> None:
    """The mock screener answers no rows: the full refresh fails in its universe stage."""
    client = client_with_worker
    refresh_id = start(client, kind="full").json()["refreshId"]
    join_runs()
    body = current(client)
    assert body["refresh"] is None
    assert body["last"]["id"] == refresh_id
    assert (body["last"]["status"], body["last"]["stage"]) == ("failed", "universe")
    assert body["last"]["message"] == body["error"] == "ValueError: screener returned no rows"


def test_api_without_worker_503(client_without_worker: TestClient) -> None:
    client = client_without_worker
    response = start(client, kind="full")
    assert response.status_code == 503
    assert response.json() == {"detail": "no refresh worker: start the server with the vendor keys"}
    assert current(client) == {"refresh": None, "last": None, "error": None}
    assert client.post("/api/refresh/cancel", headers=POST).json() == {"cancelled": True}


def test_post_without_the_request_header_403(client_with_worker: TestClient, db_path: Path) -> None:
    """D11: a cross-site form cannot send a custom header, nor a cross-origin script without a
    CORS preflight the app never answers."""
    client = client_with_worker
    for headers in ({}, {"X-Fairband-Request": "0"}):
        response = client.post("/api/refresh", json={"kind": "full"}, headers=headers)
        assert (response.status_code, response.json()) == (403, MISSING_HEADER)
        response = client.post("/api/refresh/cancel", headers=headers)
        assert (response.status_code, response.json()) == (403, MISSING_HEADER)
    with closing(connect(db_path)) as conn:
        assert latest_refresh(conn) is None


def test_untrusted_host_400(client_with_worker: TestClient) -> None:
    """D11: a page on another name that resolves to 127.0.0.1 (DNS rebinding) cannot read."""
    client = client_with_worker
    for path in ("/", "/api/screen", "/api/refresh/current"):
        response = client.get(path, headers={"Host": "evil.example"})
        assert response.status_code == 400, path
    assert (
        client.post("/api/refresh/cancel", headers={**POST, "Host": "evil.example"}).status_code
        == 400
    )
    for host in ("127.0.0.1:8470", "localhost:8470", "localhost"):
        assert client.get("/api/refresh/current", headers={"Host": host}).status_code == 200


def test_app_js_posts_with_the_request_header() -> None:
    script = resources.files("fairband.web").joinpath("static", "app.js").read_text("utf-8")
    assert "'X-Fairband-Request': '1'" in script


# --- python -m fairband serve ----------------------------------------------------------------


def serve_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[Any]:
    """Point ``serve`` at a temporary data and config directory, with no key in the environment,
    and stand in for uvicorn: while "serving", it starts a full refresh through the app and reads
    the result; the list gets the response and the body."""
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)
    monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)
    served: list[Any] = []

    def run_app(app: Any, **kwargs: Any) -> None:
        with TestClient(app, base_url=HOST) as client:
            served.append(start(client, kind="full"))
            join_runs()
            served.append(current(client))

    monkeypatch.setattr(uvicorn, "run", run_app)
    return served


def test_serve_without_an_fmp_key_has_no_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The screen is served all the same; the keys file's mode is checked as the command does."""
    served = serve_env(monkeypatch, tmp_path)
    keys_file = tmp_path / "config" / "fairband" / "keys.toml"
    keys_file.parent.mkdir(parents=True)
    keys_file.write_text('[keys]\ngurufocus = "fakegfhalf:fakegfhalf2"\n')
    keys_file.chmod(0o644)
    with caplog.at_level(logging.WARNING):
        assert cli.main(["serve"]) == 0
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        f"{keys_file} has mode 0644: other users can read it; chmod 600 it",
        f"{MissingKey('fmp')}; the screen is served without refreshes",
    ]
    response, body = served
    assert response.status_code == 503
    assert body == {"refresh": None, "last": None, "error": None}
    assert "fakegfhalf" not in caplog.text


def test_serve_builds_a_worker_with_the_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture, fmp: Fmp
) -> None:
    served = serve_env(monkeypatch, tmp_path)
    monkeypatch.setenv("FAIRBAND_FMP_KEY", KEY)
    built: list[str | None] = []

    def clients(keys: Keys, policy: Policy) -> tuple[Fmp, None, tuple[str, ...]]:
        built.append(keys.fmp)
        return fmp, None, (KEY,)

    monkeypatch.setattr(cli, "build_clients", clients)
    with caplog.at_level(logging.WARNING):
        assert cli.main(["serve"]) == 0
    assert built == [KEY]
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        "no GuruFocus key: the moat score and the GuruFocus EPS are not fetched"
    ]
    response, body = served
    assert (response.status_code, response.json()) == (200, {"refreshId": 1})
    # The mock FMP's screener has no rows: the worker ran the refresh, and it failed on that.
    assert body["last"]["status"] == "failed"
    assert body["error"] == "ValueError: screener returned no rows"
    assert KEY not in caplog.text
