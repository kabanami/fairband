"""The refresh routes and the D11 guards through the app, on a temporary migrated database, with a
``RefreshWorker`` over FMP on a mock transport, and the ``serve`` command that builds them.
``fetch_company`` is replaced by a gate that holds each fetch until the test releases it, so a run
stays in its fetch stage while the test looks."""

import logging
import sqlite3
import threading
import time
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
from fairband.engine.route import refusal_result
from fairband.policy import Policy, load_policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.policy.tax import load_tax_table
from fairband.refresh import run as run_module
from fairband.refresh.fetch import FetchOutcome
from fairband.refresh.run import Progress, Refresh
from fairband.refresh.worker import RefreshWorker
from fairband.store.db import connect, migrate
from fairband.store.refreshes import create_refresh, finish_refresh, items, latest_refresh
from fairband.store.settings import write_settings
from fairband.store.snapshots import insert_snapshot, latest_snapshot
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
    fetched with nothing called."""

    def __init__(self) -> None:
        self._entered = threading.Semaphore(0)
        self.release = threading.Event()

    def __call__(self, conn: Any, fmp: Any, gf: Any, symbol: str, *rest: Any) -> FetchOutcome:
        self._entered.release()
        self.release.wait(5)
        return FetchOutcome(symbol, 0, 0, (), None)

    def wait_entered(self, fetches: int) -> None:
        """Wait until ``fetches`` fetches have started."""
        for _ in range(fetches):
            assert self._entered.acquire(timeout=5)


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

    worker = RefreshWorker(make_refresh)  # waits up to 5 s for a given-up fetch to end
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
    gate.wait_entered(2)  # both fetching: the run starts no other until one ends
    assert current(client) == {
        "refresh": {
            "id": 1,
            "kind": "scoped",
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
    gate.wait_entered(1)
    response = start(client, kind="full")
    assert (response.status_code, response.json()) == (409, {"running": first})
    gate.release.set()
    join_runs()
    assert current(client)["last"]["status"] == "done"

    # A refresh another process runs (the command) is refused the same way.
    with closing(connect(db_path)) as conn:
        other = create_refresh(
            conn, "scoped", ["BOLT"], "fairband-policy-v1", METHOD_VERSION, NOW, EMPTY_SETTINGS_HASH
        )
    response = start(client, kind="scoped", symbols=["ACME"])
    assert (response.status_code, response.json()) == (409, {"running": other})


def test_api_second_refresh_refused_at_once(client_with_worker: TestClient, gate: Gate) -> None:
    """During a live run the 409 comes at once: the worker's 5-second wait is only for the
    fetches a run that already ended gave up."""
    client = client_with_worker
    first = start(client, kind="scoped", symbols=["ACME"]).json()["refreshId"]
    gate.wait_entered(1)
    began = time.monotonic()
    response = start(client, kind="scoped", symbols=["BOLT"])
    elapsed = time.monotonic() - began
    assert (response.status_code, response.json()) == (409, {"running": first})
    assert elapsed < 0.5


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"kind": "weekly"}, "unknown refresh kind: weekly"),
        ({"kind": "scoped"}, "a scoped refresh needs symbols"),
        ({"kind": "scoped", "symbols": []}, "a scoped refresh needs symbols"),
        ({"kind": "price", "symbols": ["ACME"]}, "a price refresh takes no symbols"),
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


@pytest.mark.parametrize(
    ("content", "detail"),
    [
        ('{"symbols": ["ACME"]}', "kind: Field required"),
        ('{"kind": 3}', "kind: Input should be a valid string"),
        ('{"kind": "scoped", "symbols": "ACME"}', "symbols: Input should be a valid list"),
        ('{"kind": "scoped", "symbols": [3]}', "symbols.0: Input should be a valid string"),
        ('{"kind": ', "body: JSON decode error"),
        ("", "body: Field required"),
    ],
)
def test_api_invalid_body_400(
    client_with_worker: TestClient, db_path: Path, content: str, detail: str
) -> None:
    headers = {**POST, "Content-Type": "application/json"}
    response = client_with_worker.post("/api/refresh", content=content, headers=headers)
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


def test_api_price_refresh_starts(client_with_worker: TestClient, db_path: Path) -> None:
    """With no universe yet, the price refresh quotes every company with a snapshot. The mock
    FMP answers the quote 404: ACME fails and keeps its snapshot, and the run is done."""
    with closing(connect(db_path)) as conn:
        scoped = create_refresh(
            conn, "scoped", ["ACME"], "fairband-policy-v1", METHOD_VERSION, NOW, EMPTY_SETTINGS_HASH
        )
        refused = refusal_result("ACME", "no universe deciles yet", load_policy(), NOW.date())
        insert_snapshot(conn, refused, scoped, clock=lambda: NOW)
        finish_refresh(conn, scoped, "done", NOW)
    client = client_with_worker
    response = start(client, kind="price")
    assert (response.status_code, response.json()) == (200, {"refreshId": scoped + 1})
    join_runs()
    last = current(client)["last"]
    assert (last["id"], last["kind"], last["status"], last["stage"]) == (
        scoped + 1,
        "price",
        "done",
        "done",
    )
    assert last["calibration"] == {"total": 1, "repriced": 0, "failed": 1, "skipped": 0}
    with closing(connect(db_path)) as conn:
        [item] = items(conn, scoped + 1)
        snapshot = latest_snapshot(conn, "ACME")
    assert (item.symbol, item.status) == ("ACME", "failed")
    assert item.error is not None and item.error.startswith("quote failed: VendorError: GET ")
    assert "404" in item.error and KEY not in item.error
    assert snapshot is not None and snapshot.refresh_id == scoped  # no new row


def test_api_without_worker_503(client_without_worker: TestClient) -> None:
    client = client_without_worker
    response = start(client, kind="full")
    assert response.status_code == 503
    assert response.json() == {"detail": "no refresh worker"}
    assert current(client) == {"refresh": None, "last": None, "error": None}
    assert client.post("/api/refresh/cancel", headers=POST).json() == {"cancelled": True}


def test_make_refresh_reads_the_overlay_per_run(db_path: Path) -> None:
    """The server's worker builds each run under the effective policy read as it starts: a
    setting saved between two runs is the second's. Without keys it builds no client."""
    tax = load_tax_table()

    def conn_factory() -> sqlite3.Connection:
        return connect(db_path)

    first = cli.make_refresh(conn_factory, None, tax, threading.Event(), lambda p: None)
    with closing(connect(db_path)) as conn:
        saved = write_settings(conn, {"required_return": 0.1}, None, NOW)
    second = cli.make_refresh(conn_factory, None, tax, threading.Event(), lambda p: None)
    assert first._policy.settings_hash == EMPTY_SETTINGS_HASH
    assert second._policy.settings_hash == saved.settings_hash != EMPTY_SETTINGS_HASH
    assert (first._policy.required_return, second._policy.required_return) == (0.09, 0.1)
    assert (second._fmp, second._gf, second._secrets) == (None, None, ())
    second.close()  # no client to close


def test_make_refresh_builds_the_clients_from_the_effective_policy(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With an FMP key each run builds clients of its own, from the policy it runs under (the
    pace is a setting), and ``Refresh.close`` closes them, once."""
    closed: list[str] = []

    class Client:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            closed.append(self.name)

    built: list[tuple[Keys, Policy]] = []

    def clients(keys: Keys, policy: Policy) -> tuple[Any, Any, tuple[str, ...]]:
        built.append((keys, policy))
        return Client("fmp"), Client("gf"), (KEY,)

    monkeypatch.setattr(cli, "build_clients", clients)
    with closing(connect(db_path)) as conn:
        saved = write_settings(conn, {"required_return": 0.1}, None, NOW)
    keys = Keys(fmp=KEY, gurufocus=None)
    refresh = cli.make_refresh(
        lambda: connect(db_path), keys, load_tax_table(), threading.Event(), lambda p: None
    )
    [(given, policy)] = built
    assert given is keys and policy == refresh._policy
    assert policy.settings_hash == saved.settings_hash
    assert refresh._secrets == (KEY,) and closed == []
    refresh.close()
    refresh.close()
    assert closed == ["fmp", "gf"]


def test_start_full_without_a_key_is_400_not_503(
    tmp_path: Path, db_path: Path, policy: Policy
) -> None:
    """The server builds its worker without an FMP key too: a refresh that fetches is a 400 that
    names the keys file, before any record; a revalue runs, keyless."""
    tax = load_tax_table()
    worker = RefreshWorker(
        lambda cancel, on_progress: cli.make_refresh(
            lambda: connect(db_path), None, tax, cancel, on_progress
        )
    )
    with make_client(tmp_path, db_path, policy, worker) as client:
        response = start(client, kind="full")
        assert (response.status_code, response.json()) == (400, {"detail": str(MissingKey("fmp"))})
        assert response.json()["detail"].startswith("no fmp key")
        with closing(connect(db_path)) as conn:
            assert latest_refresh(conn) is None
        response = start(client, kind="revalue")
        assert (response.status_code, response.json()) == (200, {"refreshId": 1})
        join_runs()
        body = current(client)
    last = body["last"]
    assert (last["kind"], last["status"], body["error"]) == ("revalue", "done", None)


def test_start_under_settings_the_policy_no_longer_knows_is_400(
    tmp_path: Path, db_path: Path, policy: Policy
) -> None:
    """A stored setting the policy file does not know: the worker cannot build the run's policy,
    so the start is a 400 naming the setting, before any record, and the server stays up."""
    tax = load_tax_table()
    with closing(connect(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO settings (name, value, changed_at) VALUES ('gone', '1', ?)",
            (NOW.isoformat(),),
        )
    worker = RefreshWorker(
        lambda cancel, on_progress: cli.make_refresh(
            lambda: connect(db_path), None, tax, cancel, on_progress
        )
    )
    with make_client(tmp_path, db_path, policy, worker) as client:
        response = start(client, kind="revalue")
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail.startswith("settings: gone: ") and "reset it on the Settings page" in detail
        assert current(client) == {"refresh": None, "last": None, "error": None}


def test_start_closes_the_previous_runs_clients(db_path: Path, policy: Policy) -> None:
    """Each run holds its own clients until the next start closes them, once the run's thread
    has ended, and closes them once; a run refused at its start closes its own at once."""
    tax = load_tax_table()
    closed: list[int] = []
    made: list[Refresh] = []

    def make_refresh(cancel: threading.Event, on_progress: Callable[[Progress], None]) -> Refresh:
        number = len(made) + 1
        refresh = Refresh(
            lambda: connect(db_path),
            None,
            None,
            policy,
            tax,
            lambda: NOW,
            cancel,
            on_progress,
            (),
            lambda: closed.append(number),
        )
        made.append(refresh)
        return refresh

    worker = RefreshWorker(make_refresh)
    assert worker.start("revalue") == 1
    join_runs()
    assert closed == []
    with pytest.raises(ValueError, match="no fmp key"):
        worker.start("full")  # the first run's clients close; the second, refused, closes its own
    assert closed == [1, 2]
    assert worker.start("revalue") == 2  # the third Refresh; the first's are closed already
    join_runs()
    assert closed == [1, 2]
    assert worker.start("revalue") == 3
    join_runs()
    assert (closed, len(made)) == ([1, 2, 3], 4)


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


def test_controls_js_calibration_reads_flagged() -> None:
    """The page's status line counts the companies valued of those admitted (goal 7), and its
    Details ▾ names those a classifier check flagged (growth-routes spec 6.1):
    ``3 of 4 valued``, then ``3 flagged by a classifier check`` in the menu. The browser check
    renders it."""
    script = resources.files("fairband.web").joinpath("static", "controls.js").read_text("utf-8")
    assert "count(c.valued), ' of ', count(c.total), ' valued'" in script
    assert "count(c.flagged) + ' flagged by a classifier check'" in script


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


def test_serve_without_an_fmp_key_runs_a_revalue_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The screen is served all the same, with a worker that refuses a full refresh (400) and
    builds no client; the keys file's mode is checked as the command does."""
    served = serve_env(monkeypatch, tmp_path)
    keys_file = tmp_path / "config" / "fairband" / "keys.toml"
    keys_file.parent.mkdir(parents=True)
    keys_file.write_text('[keys]\ngurufocus = "fakegfhalf:fakegfhalf2"\n')
    keys_file.chmod(0o644)

    def no_clients(*args: Any) -> Any:
        raise AssertionError("no FMP key: the worker builds no vendor client")

    monkeypatch.setattr(cli, "build_clients", no_clients)
    with caplog.at_level(logging.WARNING):
        assert cli.main(["serve"]) == 0
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        f"{keys_file} has mode 0644: other users can read it; chmod 600 it",
        f"{MissingKey('fmp')}; the server runs a revalue only",
    ]
    response, body = served
    assert (response.status_code, response.json()) == (400, {"detail": str(MissingKey("fmp"))})
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
