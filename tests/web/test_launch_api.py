"""The launch routes (spec 2026-11-16 agent launch, 6, 8, 9 and 12): ``POST /api/launches`` stores
a launch and runs the window command, ``GET /api/launches/{id}`` reads it, and the launcher's two
routes, ``GET /api/launches/{id}/command`` and ``POST /api/launches/{id}/status``, give the agent's
words and take its reports. The app's start marks failed a launch a stopped server left
``opening``; the detail read's open ``item`` carries its newest launch; ``serve`` hands the app an
opener and the port of ``--port``.

The opener is a double: its runner records the words it is given and answers how the program
ended, and its finder finds every program unless a test says otherwise, so nothing here opens a
window, starts an agent or calls ``system_opener().run``. A launch still ``opening`` is made
through the store."""

import logging
import sqlite3
import subprocess
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from support.web import HEADER, HOST, NOW, _settings

from fairband import __main__ as cli
from fairband.launch.command import Opener
from fairband.launch.settings import write_launch_file
from fairband.policy import Policy
from fairband.store.db import connect, transaction
from fairband.store.inbox import complete_item, decline_item, drop_item, post_item, work_item
from fairband.store.launches import STOPPED, InFlight, State, insert_launch, launch, move_launch
from fairband.store.ledger import OWNER
from fairband.web.app import create_app
from fairband.web.identity import ACTOR_HEADER, PRINCIPAL_HEADER

AGENT = HEADER | {PRINCIPAL_HEADER: "agent", ACTOR_HEADER: "claude-opus-5-5"}
WT_LINE = "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e"
LAUNCHER = "/pkg/fairband/launch/launcher.sh"
PYTHON = "/usr/bin/python3"
PORT = 8470
OWNERS = "a launch is the owner's"
NO_WINDOW = "this server opens no window"
NOT_SET_UP = "launching is not set up: see Settings, Agents"
NAMES_NOTHING = "a launch names an item or a test"
REPORTS = "a launcher reports started, ended or failed"
NO_REASON = "a failed report gives its reason"
NO_EXIT_CODE = "an ended report gives its exit code"
# The agent's words for the launch file of ``served``, the prompt's {item} left to fill.
ARGV = ["claude", "--model", "claude-opus-5-5", "--effort", "xhigh", "--permission-mode", "auto"]


class Runner:
    """The window command's runner: it records each list of words, raises ``raises`` where a test
    sets it, calls ``during`` with them (a launcher that reports while the command runs), and
    answers ``returncode`` with ``stderr``."""

    def __init__(self) -> None:
        self.ran: list[list[str]] = []
        self.returncode = 0
        self.stderr = b""
        self.during: Callable[[list[str]], None] | None = None
        self.raises: Exception | None = None

    def __call__(self, words: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
        assert isinstance(words, list), "the window command runs as a list of words"
        self.ran.append(list(words))
        if self.raises is not None:
            raise self.raises
        if self.during is not None:
            self.during(list(words))
        return subprocess.CompletedProcess(list(words), self.returncode, None, self.stderr)


class Finder:
    """The program finder: a path for every program but those in ``missing``; it raises
    ``raises`` where a test sets it."""

    def __init__(self) -> None:
        self.missing: set[str] = set()
        self.raises: Exception | None = None

    def __call__(self, program: str) -> str | None:
        if self.raises is not None:
            raise self.raises
        return None if program in self.missing else f"/found/{program}"


class Clock:
    """The app's clock, which a test moves."""

    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def runner() -> Runner:
    return Runner()


@pytest.fixture
def finder() -> Finder:
    return Finder()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """The config folder of the apps built here, as ``support.web._settings`` names it."""
    return tmp_path / "config"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The user's home, where ``~`` in the launch file's folder leads."""
    found = tmp_path / "home"
    monkeypatch.setenv("HOME", str(found))
    return found


def _opener(runner: Runner, finder: Finder, launcher: str = LAUNCHER) -> Opener:
    return Opener(run=runner, which=finder, python=PYTHON, launcher=launcher, environ={})


def _app(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    clock: Clock,
    opener: Opener | None,
    port: int | None = PORT,
    conn_factory: Callable[[], sqlite3.Connection] | None = None,
) -> FastAPI:
    return create_app(
        _settings(tmp_path, db_path),
        policy,
        conn_factory or (lambda: connect(db_path)),
        clock=clock,
        opener=opener,
        port=port,
    )


def _set_up(config_dir: Path) -> None:
    """The launch file of the founder's machine: the Windows Terminal line and every field of
    Claude Code's set."""
    write_launch_file(
        config_dir,
        {
            "window_command": WT_LINE,
            "claude.model": "claude-opus-5-5",
            "claude.effort": "xhigh",
            "claude.permission_mode": "auto",
        },
    )


@pytest.fixture
def served(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    runner: Runner,
    finder: Finder,
    clock: Clock,
    config_dir: Path,
) -> Iterator[TestClient]:
    """A client of an app on port 8470 with the double opener, whose launch file is set up."""
    _set_up(config_dir)
    client = TestClient(
        _app(tmp_path, db_path, policy, clock, _opener(runner, finder)), base_url=HOST
    )
    yield client
    client.close()


def _item(client: TestClient, symbol: str = "AAPL") -> int:
    """A pending work item for ``symbol``, posted by the owner; its id."""
    body = {"symbol": symbol, "mode": "full report", "note": ""}
    response = client.post("/api/inbox", json=body, headers=HEADER)
    assert response.status_code == 201, response.text
    item_id: int = response.json()["id"]
    return item_id


def _claim(client: TestClient, item_id: int) -> None:
    response = client.post("/api/inbox/claim", json={"itemId": item_id}, headers=AGENT)
    assert response.status_code == 200, response.text


def _launch(
    client: TestClient, body: dict[str, Any], headers: dict[str, str] = HEADER
) -> httpx.Response:
    return client.post("/api/launches", json=body, headers=headers)


def _made(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    """A launch posted with ``body`` and answered 201."""
    response = _launch(client, body)
    assert response.status_code == 201, response.text
    made: dict[str, Any] = response.json()
    return made


def _status(
    client: TestClient, launch_id: int, body: dict[str, Any], headers: dict[str, str] = HEADER
) -> httpx.Response:
    return client.post(f"/api/launches/{launch_id}/status", json=body, headers=headers)


def _command(client: TestClient, launch_id: int) -> httpx.Response:
    return client.get(f"/api/launches/{launch_id}/command")


def _rows(db_path: Path) -> list[tuple[int, int | None, str]]:
    """Every launch as ``(id, item_id, state)``, in id order."""
    with closing(connect(db_path)) as conn:
        found = conn.execute("SELECT id, item_id, state FROM launches ORDER BY id").fetchall()
    return [(r["id"], r["item_id"], r["state"]) for r in found]


def _opening(db_path: Path, item_id: int | None) -> int:
    """A launch for ``item_id`` made through the store at ``NOW`` and left ``opening``; its id."""
    with closing(connect(db_path)) as conn:
        return insert_launch(conn, item_id, "claude", NOW).id


def _words(title: str, launch_id: int, port: int = PORT) -> list[str]:
    """The words the Windows Terminal line runs with ``title`` and the launcher's six words."""
    line = ["wt.exe", "-w", "0", "new-tab", "--title", title, "wsl.exe", "-d", "Ubuntu", "-e"]
    return [*line, "bash", "-l", LAUNCHER, PYTHON, str(port), str(launch_id)]


def _answer(launch_id: int, item_id: int | None, **changes: Any) -> dict[str, Any]:
    """The launch as the API sends it: made, moved and read at ``NOW``, ``opened``, its item
    pending; ``changes`` over that."""
    answer = {
        "id": launch_id,
        "itemId": item_id,
        "test": item_id is None,
        "agent": "claude",
        "state": "opened",
        "stage": None,
        "detail": None,
        "exitCode": None,
        "createdAt": NOW.isoformat(),
        "updatedAt": NOW.isoformat(),
        "ageSeconds": 0,
        "overdue": False,
        "itemState": None if item_id is None else "pending",
        "claimedBy": None,
    }
    return answer | changes


def _refused(response: httpx.Response, status: int, detail: str) -> None:
    assert (response.status_code, response.json()) == (status, {"detail": detail})


# ------------------------------------------------------------------ the launch


def test_a_launch_for_a_pending_item_runs_the_window_command_and_answers_opened(
    served: TestClient, runner: Runner
) -> None:
    """The words run are the saved window command's, the title the stored item's symbol, then
    ``bash -l``, the launcher, the server's Python, the app's port and the launch's id."""
    item_id = _item(served)
    response = _launch(served, {"itemId": item_id})
    assert response.status_code == 201, response.text
    made = response.json()
    assert made == _answer(made["id"], item_id)
    assert runner.ran == [_words("Fairband-AAPL", made["id"])]
    assert served.get(f"/api/launches/{made['id']}").json() == made


def test_a_window_command_whose_program_is_not_found_fails_the_launch_and_runs_nothing(
    served: TestClient, runner: Runner, finder: Finder
) -> None:
    finder.missing = {"wt.exe"}
    item_id = _item(served)
    made = _made(served, {"itemId": item_id})
    detail = "`wt.exe` was not found"
    assert made == _answer(made["id"], item_id, state="failed", stage="window", detail=detail)
    assert runner.ran == []


def test_a_window_command_that_ends_with_another_exit_code_fails_the_launch(
    served: TestClient, runner: Runner
) -> None:
    runner.returncode = 1
    runner.stderr = "The system cannot find the file\r\n".encode("utf-16-le")
    made = _made(served, {"itemId": _item(served)})
    sentence = "the window command ended with exit code 1: The system cannot find the file"
    assert (made["state"], made["stage"], made["detail"]) == ("failed", "window", sentence)
    assert len(runner.ran) == 1


def test_a_word_that_cannot_cross_the_window_fails_the_launch_before_anything_runs(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    runner: Runner,
    finder: Finder,
    clock: Clock,
    config_dir: Path,
) -> None:
    _set_up(config_dir)
    opener = _opener(runner, finder, launcher="/opt/my tools/launcher.sh")
    with closing(TestClient(_app(tmp_path, db_path, policy, clock, opener), base_url=HOST)) as c:
        made = _made(c, {"test": True})
    sentence = (
        "`/opt/my tools/launcher.sh` cannot cross the window: it holds a character other than "
        "letters, digits and _ . / : @ + -"
    )
    assert (made["state"], made["stage"], made["detail"]) == ("failed", "window", sentence)
    assert runner.ran == []


@pytest.mark.parametrize(
    ("where", "error", "text"),
    [
        # a NUL byte in a word of the window command after the first, as subprocess.run raises it
        ("run", ValueError("embedded null byte"), "embedded null byte"),
        ("which", RuntimeError("the finder broke"), "the finder broke"),
        ("which", RuntimeError(), "RuntimeError"),  # an error with no text names its kind
    ],
)
def test_an_unexpected_error_in_the_window_step_fails_the_launch_and_frees_its_item(
    served: TestClient,
    runner: Runner,
    finder: Finder,
    db_path: Path,
    caplog: pytest.LogCaptureFixture,
    where: str,
    error: Exception,
    text: str,
) -> None:
    """The launch is ``failed`` at the window stage with a sentence, not left ``opening``, which
    would hold its item until the server restarted; the traceback is logged once, under the
    launch's id and no setting's value."""
    item_id = _item(served)
    if where == "run":
        runner.raises = error
    else:
        finder.raises = error
    with caplog.at_level(logging.WARNING, logger="fairband.web"):
        made = _made(served, {"itemId": item_id})
    sentence = f"the window command could not start: {text}"
    assert made == _answer(made["id"], item_id, state="failed", stage="window", detail=sentence)
    assert _rows(db_path) == [(made["id"], item_id, "failed")]
    (warning,) = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warning.levelno == logging.WARNING and warning.exc_info is not None
    assert f"launch {made['id']}" in warning.getMessage()
    assert "wt.exe" not in warning.getMessage()
    runner.raises = finder.raises = None
    second = _made(served, {"itemId": item_id})
    assert second["state"] == "opened"


def test_a_test_launch_has_no_item_and_its_window_is_titled_fairband_test(
    served: TestClient, runner: Runner, db_path: Path
) -> None:
    """A test neither blocks nor is blocked: a second test opens a second window."""
    first = _made(served, {"test": True})
    assert first == _answer(first["id"], None)
    second = _made(served, {"test": True})
    assert runner.ran == [
        _words("Fairband-test", first["id"]),
        _words("Fairband-test", second["id"]),
    ]
    assert _rows(db_path) == [(first["id"], None, "opened"), (second["id"], None, "opened")]


def test_the_launch_is_committed_before_the_window_command_runs(
    served: TestClient, runner: Runner, db_path: Path
) -> None:
    """A launcher that reports before the window command has returned finds its launch, the
    server holding no write lock while the command runs; the launch stays as the launcher left
    it. The second connection waits for no lock, so a lock held would fail here at once."""
    seen: list[State] = []

    def launcher_reports(words: list[str]) -> None:
        with closing(connect(db_path)) as conn:
            conn.execute("PRAGMA busy_timeout = 0")
            seen.append(launch(conn, int(words[-1])).state)
            move_launch(conn, int(words[-1]), "started", NOW)

    runner.during = launcher_reports
    item_id = _item(served)
    made = _made(served, {"itemId": item_id})
    assert seen == ["opening"]
    assert made == _answer(made["id"], item_id, state="started")


def test_a_window_command_that_fails_after_the_launcher_reported_answers_the_launch_as_it_is(
    served: TestClient, runner: Runner, db_path: Path
) -> None:
    """The record refuses ``started`` to ``failed``; the launcher's word is the later fact, and
    the route answers it, not a 500."""

    def launcher_reports(words: list[str]) -> None:
        with closing(connect(db_path)) as conn:
            move_launch(conn, int(words[-1]), "started", NOW)

    runner.during = launcher_reports
    runner.returncode = 1
    made = _made(served, {"test": True})
    assert made == _answer(made["id"], None, state="started")


def test_the_items_check_and_the_insert_are_one_transaction_before_the_window_command(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    runner: Runner,
    finder: Finder,
    clock: Clock,
    config_dir: Path,
) -> None:
    """Review Focus 4, in the route: the item's read and the launch's insert sit inside one
    ``BEGIN IMMEDIATE``, which commits before the window command runs."""
    _set_up(config_dir)
    statements: list[str] = []

    def traced() -> sqlite3.Connection:
        conn = connect(db_path)
        conn.set_trace_callback(statements.append)
        return conn

    runner.during = lambda words: statements.append("RUN")
    app = _app(tmp_path, db_path, policy, clock, _opener(runner, finder), conn_factory=traced)
    with closing(TestClient(app, base_url=HOST)) as client:
        item_id = _item(client)
        statements.clear()
        _made(client, {"itemId": item_id})
    begin = statements.index("BEGIN IMMEDIATE")
    check = next(i for i, s in enumerate(statements) if s.startswith("SELECT * FROM work_items"))
    insert = next(i for i, s in enumerate(statements) if s.startswith("INSERT INTO launches"))
    commit = statements.index("COMMIT")
    assert begin < check < insert < commit < statements.index("RUN")


def test_a_second_launch_while_the_first_is_in_flight_is_a_409_and_runs_nothing(
    served: TestClient, runner: Runner, clock: Clock, db_path: Path
) -> None:
    """Review Focus 4: two posts for one item open one window."""
    item_id = _item(served)
    first = _made(served, {"itemId": item_id})
    clock.now = NOW + timedelta(seconds=20)
    response = _launch(served, {"itemId": item_id})
    _refused(response, 409, "a window for this request opened 20 seconds ago")
    assert _rows(db_path) == [(first["id"], item_id, "opened")]
    assert len(runner.ran) == 1


def test_the_check_and_the_insert_hold_the_write_lock_together(
    served: TestClient, db_path: Path
) -> None:
    """Review Focus 4, at the store's step: while one connection holds the write lock around the
    item's check and the insert, a second cannot insert at all; once the first commits, the
    second's insert finds the first launch in flight."""
    item_id = _item(served)
    with closing(connect(db_path)) as first, closing(connect(db_path)) as second:
        second.execute("PRAGMA busy_timeout = 0")
        with transaction(first, immediate=True):
            assert work_item(first, item_id).state == "pending"
            insert_launch(first, item_id, "claude", NOW)
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                insert_launch(second, item_id, "claude", NOW)
        with pytest.raises(InFlight, match="^a window for this request opened 0 seconds ago$"):
            insert_launch(second, item_id, "claude", NOW)
    assert [row[1:] for row in _rows(db_path)] == [(item_id, "opening")]


def test_a_second_launch_is_taken_after_the_first_failed(
    served: TestClient, runner: Runner, finder: Finder, db_path: Path
) -> None:
    item_id = _item(served)
    finder.missing = {"wt.exe"}
    first = _made(served, {"itemId": item_id})
    assert first["state"] == "failed"
    finder.missing = set()
    second = _made(served, {"itemId": item_id})
    assert second["state"] == "opened"
    assert _rows(db_path) == [(first["id"], item_id, "failed"), (second["id"], item_id, "opened")]
    assert runner.ran == [_words("Fairband-AAPL", second["id"])]


# ------------------------------------------------------------------ the launch's refusals


def test_an_agents_launch_is_a_403_and_runs_nothing(
    served: TestClient, runner: Runner, db_path: Path
) -> None:
    _refused(_launch(served, {"itemId": _item(served)}, AGENT), 403, OWNERS)
    _refused(_launch(served, {"test": True}, AGENT), 403, OWNERS)
    assert runner.ran == [] and _rows(db_path) == []


@pytest.mark.parametrize("missing", ["opener", "port"])
def test_an_app_that_opens_no_window_answers_503_and_runs_nothing(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    runner: Runner,
    finder: Finder,
    clock: Clock,
    config_dir: Path,
    missing: str,
) -> None:
    _set_up(config_dir)
    opener = None if missing == "opener" else _opener(runner, finder)
    port = None if missing == "port" else PORT
    with closing(
        TestClient(_app(tmp_path, db_path, policy, clock, opener, port), base_url=HOST)
    ) as c:
        _refused(_launch(c, {"test": True}), 503, NO_WINDOW)
    assert runner.ran == [] and _rows(db_path) == []


def test_the_shared_client_opens_no_window(client: TestClient, config_dir: Path) -> None:
    """The app the other tests build has no opener: it answers 503 to a launch."""
    _set_up(config_dir)
    _refused(_launch(client, {"test": True}), 503, NO_WINDOW)


@pytest.mark.parametrize(
    ("text", "sentence"),
    [
        ("not json", "launch.json is not valid JSON (line 1)"),
        (
            '{"window_command": "wt.exe", "claude": {"effort": "extreme"}}',
            "launch.json: `claude.effort` is `extreme`; it is one of low, medium, high, xhigh, max",
        ),
    ],
)
def test_a_launch_file_the_server_cannot_use_refuses_the_launch_with_its_sentence(
    served: TestClient,
    runner: Runner,
    config_dir: Path,
    db_path: Path,
    text: str,
    sentence: str,
) -> None:
    (config_dir / "launch.json").write_text(text, encoding="utf-8")
    _refused(_launch(served, {"test": True}), 400, sentence)
    assert runner.ran == [] and _rows(db_path) == []


@pytest.mark.parametrize("window_command", [None, "", "   "])
def test_a_launch_with_no_window_command_is_refused_and_runs_nothing(
    served: TestClient,
    runner: Runner,
    config_dir: Path,
    db_path: Path,
    window_command: str | None,
) -> None:
    """No file is every default, so launching is off; so is a window command of blanks, whose
    six added words would otherwise run the launcher inside the server."""
    if window_command is None:
        (config_dir / "launch.json").unlink()
    else:
        write_launch_file(config_dir, {"window_command": window_command})
    _refused(_launch(served, {"test": True}), 400, NOT_SET_UP)
    assert runner.ran == [] and _rows(db_path) == []


@pytest.mark.parametrize("body", [{}, {"test": False}, {"itemId": 1, "test": True}])
def test_a_launch_names_an_item_or_a_test(
    served: TestClient, runner: Runner, db_path: Path, body: dict[str, Any]
) -> None:
    _item(served)
    _refused(_launch(served, body), 400, NAMES_NOTHING)
    assert runner.ran == [] and _rows(db_path) == []


@pytest.mark.parametrize("body", [{"itemId": "1"}, {"itemId": True}, {"test": "true"}])
def test_a_launch_takes_an_items_number_and_a_tests_boolean_not_text_that_reads_as_one(
    served: TestClient, runner: Runner, db_path: Path, body: dict[str, Any]
) -> None:
    """Item 1 exists, so ``"1"`` and ``true`` would each launch it if they were read as 1."""
    _item(served)
    assert _launch(served, body).status_code == 400
    assert runner.ran == [] and _rows(db_path) == []


def test_a_launch_for_no_item_is_a_404(served: TestClient, runner: Runner, db_path: Path) -> None:
    _refused(_launch(served, {"itemId": 999}), 404, "no work item 999")
    assert runner.ran == [] and _rows(db_path) == []


def test_a_launch_for_an_item_an_agent_claimed_meanwhile_is_a_409_and_runs_nothing(
    served: TestClient, runner: Runner, db_path: Path
) -> None:
    """Review Focus 5: a session that already runs claims the item between the two posts."""
    item_id = _item(served)
    _claim(served, item_id)
    response = _launch(served, {"itemId": item_id})
    _refused(response, 409, f"item {item_id} is claimed by claude-opus-5-5")
    assert runner.ran == [] and _rows(db_path) == []


@pytest.mark.parametrize("state", ["done", "declined", "dropped"])
def test_a_launch_for_a_finished_item_is_a_409_and_runs_nothing(
    served: TestClient, runner: Runner, db_path: Path, state: str
) -> None:
    item_id = _item(served)
    with closing(connect(db_path)) as conn:
        if state == "done":
            complete_item(conn, item_id, 1, NOW)
        elif state == "declined":
            decline_item(conn, item_id, "no consensus on file", NOW)
        else:
            drop_item(conn, item_id, NOW)
    _refused(_launch(served, {"itemId": item_id}), 409, f"item {item_id} is {state}")
    assert runner.ran == [] and _rows(db_path) == []


def test_the_refusals_of_a_launch_come_in_the_tables_order(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    runner: Runner,
    finder: Finder,
    clock: Clock,
    config_dir: Path,
) -> None:
    """The agent's principal before the app that opens no window, that before the file, the file
    before the body, and the body before the item."""
    with closing(TestClient(_app(tmp_path, db_path, policy, clock, None), base_url=HOST)) as c:
        _refused(_launch(c, {}, AGENT), 403, OWNERS)
        _refused(_launch(c, {}), 503, NO_WINDOW)
    opener = _opener(runner, finder)
    with closing(TestClient(_app(tmp_path, db_path, policy, clock, opener), base_url=HOST)) as c:
        config_dir.mkdir()
        (config_dir / "launch.json").write_text("not json", encoding="utf-8")
        _refused(_launch(c, {}), 400, "launch.json is not valid JSON (line 1)")
        write_launch_file(config_dir, {"window_command": ""})
        _refused(_launch(c, {}), 400, NOT_SET_UP)
        _set_up(config_dir)
        _refused(_launch(c, {"itemId": 999, "test": True}), 400, NAMES_NOTHING)
    assert runner.ran == [] and _rows(db_path) == []


# ------------------------------------------------------------------ the read


def test_the_read_answers_its_age_and_overdue_on_the_apps_clock(
    served: TestClient, clock: Clock
) -> None:
    """Overdue at 90 seconds and not at 89 while the item is pending, never once it is claimed;
    the age is whole seconds and never below 0."""
    item_id = _item(served)
    url = f"/api/launches/{_made(served, {'itemId': item_id})['id']}"

    def read() -> tuple[Any, ...]:
        found = served.get(url).json()
        return (found["ageSeconds"], found["overdue"], found["itemState"], found["claimedBy"])

    clock.now = NOW + timedelta(seconds=89, milliseconds=999)
    assert read() == (89, False, "pending", None)
    clock.now = NOW + timedelta(seconds=90)
    assert read() == (90, True, "pending", None)
    _claim(served, item_id)
    assert read() == (90, False, "claimed", "claude-opus-5-5")
    clock.now = NOW - timedelta(seconds=5)
    assert read()[0] == 0


def test_a_test_is_overdue_while_opened_and_never_once_started(
    served: TestClient, clock: Clock
) -> None:
    made = _made(served, {"test": True})
    url = f"/api/launches/{made['id']}"
    clock.now = NOW + timedelta(seconds=90)
    found = served.get(url).json()
    assert (found["overdue"], found["itemState"], found["claimedBy"]) == (True, None, None)
    assert _status(served, made["id"], {"state": "started"}).status_code == 200
    assert served.get(url).json()["overdue"] is False


@pytest.mark.parametrize("path", ["", "/command"])
def test_a_read_of_no_launch_is_a_404(served: TestClient, path: str) -> None:
    _refused(served.get(f"/api/launches/999{path}"), 404, "no launch 999")


# ------------------------------------------------------------------ the command read


def test_the_command_read_answers_the_agents_words_and_the_folder_made_absolute(
    served: TestClient, db_path: Path, home: Path
) -> None:
    """Taken while the launch is ``opened`` and while it is still ``opening``, the window
    command not yet returned. It is a read and needs no request header."""
    item_id = _item(served)
    made = _made(served, {"itemId": item_id})
    folder = str(home / "fairband-research")
    response = _command(served, made["id"])
    assert response.status_code == 200, response.text
    assert response.json() == {
        "argv": [*ARGV, f"/fairband-research work item {item_id}"],
        "folder": folder,
    }
    other = _item(served, "HGCO")
    opening = _opening(db_path, other)
    response = _command(served, opening)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "argv": [*ARGV, f"/fairband-research work item {other}"],
        "folder": folder,
    }


def test_the_command_read_of_a_test_ends_with_the_test_prompt(
    served: TestClient, home: Path
) -> None:
    made = _made(served, {"test": True})
    assert _command(served, made["id"]).json() == {
        "argv": [*ARGV, "/fairband-research launch test"],
        "folder": str(home / "fairband-research"),
    }


@pytest.mark.parametrize(
    "reports",
    [
        [{"state": "started"}],
        [{"state": "started"}, {"state": "ended", "exitCode": 0}],
        [{"state": "failed", "detail": "`claude` was not found on the path of a login shell"}],
    ],
)
def test_the_command_read_is_refused_once_the_launch_has_moved_on(
    served: TestClient, reports: list[dict[str, Any]]
) -> None:
    made = _made(served, {"itemId": _item(served)})
    for report in reports:
        assert _status(served, made["id"], report).status_code == 200
    state = reports[-1]["state"]
    _refused(_command(served, made["id"]), 409, f"launch {made['id']} is {state}")


def test_the_command_read_is_refused_once_the_window_failed(
    served: TestClient, finder: Finder
) -> None:
    finder.missing = {"wt.exe"}
    made = _made(served, {"test": True})
    _refused(_command(served, made["id"]), 409, f"launch {made['id']} is failed")


def test_the_command_read_is_refused_once_the_item_is_no_longer_pending(
    served: TestClient, db_path: Path
) -> None:
    """A second window opened for an item an agent took meanwhile starts no second agent."""
    item_id = _item(served)
    made = _made(served, {"itemId": item_id})
    _claim(served, item_id)
    _refused(_command(served, made["id"]), 409, f"item {item_id} is claimed by claude-opus-5-5")
    with closing(connect(db_path)) as conn:
        decline_item(conn, item_id, "no consensus on file", NOW)
    _refused(_command(served, made["id"]), 409, f"item {item_id} is declined")


def test_the_command_read_with_a_file_the_server_cannot_use_is_a_400(
    served: TestClient, config_dir: Path
) -> None:
    made = _made(served, {"test": True})
    (config_dir / "launch.json").write_text("[]", encoding="utf-8")
    _refused(_command(served, made["id"]), 400, "launch.json: the file holds no object")


# ------------------------------------------------------------------ the launcher's reports


def test_a_launcher_reports_started_then_ended_with_its_exit_code(served: TestClient) -> None:
    """``started`` keeps no sentence and no exit code, whatever the report carries."""
    item_id = _item(served)
    made = _made(served, {"itemId": item_id})
    report = {"state": "started", "detail": "ignored", "exitCode": 5}
    response = _status(served, made["id"], report)
    assert response.status_code == 200, response.text
    assert response.json() == _answer(made["id"], item_id, state="started")
    response = _status(served, made["id"], {"state": "ended", "exitCode": 3})
    assert response.status_code == 200, response.text
    assert response.json() == _answer(made["id"], item_id, state="ended", exitCode=3)
    assert served.get(f"/api/launches/{made['id']}").json() == response.json()


def test_a_launcher_reports_failed_with_its_sentence_at_the_agent_stage(
    served: TestClient,
) -> None:
    made = _made(served, {"test": True})
    sentence = "`claude-nope` was not found on the path of a login shell"
    response = _status(served, made["id"], {"state": "failed", "detail": sentence})
    assert response.status_code == 200, response.text
    expected = _answer(made["id"], None, state="failed", stage="agent", detail=sentence)
    assert response.json() == expected


@pytest.mark.parametrize(
    ("report", "state"),
    [
        ({"state": "started"}, "started"),
        ({"state": "failed", "detail": "the folder /x cannot be made: denied"}, "failed"),
    ],
)
def test_a_report_on_a_launch_still_opening_is_taken(
    served: TestClient, db_path: Path, report: dict[str, Any], state: str
) -> None:
    """The window's program may report before the window command has returned."""
    item_id = _item(served)
    launch_id = _opening(db_path, item_id)
    response = _status(served, launch_id, report)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == state


def _launch_in(client: TestClient, db_path: Path, state: State) -> int:
    """A test launch in ``state``: ``opening`` through the store, the rest through the routes."""
    if state == "opening":
        return _opening(db_path, None)
    launch_id: int = _made(client, {"test": True})["id"]
    path: dict[State, list[dict[str, Any]]] = {
        "opened": [],
        "started": [{"state": "started"}],
        "ended": [{"state": "started"}, {"state": "ended", "exitCode": 0}],
        "failed": [{"state": "failed", "detail": "the program could not start"}],
    }
    for report in path[state]:
        assert _status(client, launch_id, report).status_code == 200
    return launch_id


@pytest.mark.parametrize(
    ("before", "to"),
    [
        ("opening", "ended"),
        ("opened", "ended"),
        ("started", "started"),
        ("started", "failed"),
        ("ended", "started"),
        ("ended", "ended"),
        ("ended", "failed"),
        ("failed", "started"),
        ("failed", "ended"),
        ("failed", "failed"),
    ],
)
def test_a_report_the_record_refuses_is_a_409(
    served: TestClient, db_path: Path, before: State, to: str
) -> None:
    launch_id = _launch_in(served, db_path, before)
    report = {"state": to, "detail": "a reason", "exitCode": 0}
    _refused(
        _status(served, launch_id, report), 409, f"a launch that is {before} does not become {to}"
    )
    assert served.get(f"/api/launches/{launch_id}").json()["state"] == before


@pytest.mark.parametrize("state", ["opened", "opening", "STARTED", ""])
def test_a_report_of_another_state_is_a_400(served: TestClient, state: str) -> None:
    made = _made(served, {"test": True})
    _refused(_status(served, made["id"], {"state": state}), 400, REPORTS)
    assert served.get(f"/api/launches/{made['id']}").json()["state"] == "opened"


@pytest.mark.parametrize("report", [{}, {"detail": None}, {"detail": ""}, {"detail": "  "}])
def test_a_failed_report_with_no_reason_is_a_400(
    served: TestClient, report: dict[str, Any]
) -> None:
    made = _made(served, {"test": True})
    _refused(_status(served, made["id"], {"state": "failed"} | report), 400, NO_REASON)
    assert served.get(f"/api/launches/{made['id']}").json()["state"] == "opened"


@pytest.mark.parametrize("report", [{}, {"exitCode": None}])
def test_an_ended_report_with_no_exit_code_is_a_400(
    served: TestClient, report: dict[str, Any]
) -> None:
    """Checked before the launch is looked up, and nothing is stored."""
    made = _made(served, {"test": True})
    assert _status(served, made["id"], {"state": "started"}).status_code == 200
    _refused(_status(served, made["id"], {"state": "ended"} | report), 400, NO_EXIT_CODE)
    assert served.get(f"/api/launches/{made['id']}").json()["state"] == "started"
    _refused(_status(served, 999, {"state": "ended"} | report), 400, NO_EXIT_CODE)


def test_an_agents_report_is_a_403(served: TestClient) -> None:
    made = _made(served, {"test": True})
    _refused(_status(served, made["id"], {"state": "started"}, AGENT), 403, OWNERS)
    assert served.get(f"/api/launches/{made['id']}").json()["state"] == "opened"


def test_a_report_on_no_launch_is_a_404(served: TestClient) -> None:
    _refused(_status(served, 999, {"state": "started"}), 404, "no launch 999")


# ------------------------------------------------------------------ D11


def test_a_write_without_the_request_header_is_a_403_and_the_reads_need_none(
    served: TestClient, runner: Runner, db_path: Path
) -> None:
    missing = {"detail": "missing X-Fairband-Request header"}
    response = _launch(served, {"test": True}, {})
    assert (response.status_code, response.json()) == (403, missing)
    assert runner.ran == [] and _rows(db_path) == []
    made = _made(served, {"test": True})
    response = _status(served, made["id"], {"state": "started"}, {})
    assert (response.status_code, response.json()) == (403, missing)
    assert served.get(f"/api/launches/{made['id']}").json()["state"] == "opened"
    assert _command(served, made["id"]).status_code == 200


# ------------------------------------------------------------------ the app's start


def test_a_launch_left_opening_is_failed_when_the_app_starts(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    runner: Runner,
    finder: Finder,
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A launch the launcher moved on stays as it is, and still takes its end."""
    with closing(connect(db_path)) as conn:
        item_id = post_item(conn, "AAPL", "full report", "", None, "owner", OWNER, NOW)
    left = _opening(db_path, item_id)
    started = _opening(db_path, None)
    with closing(connect(db_path)) as conn:
        move_launch(conn, started, "started", NOW)
    clock.now = NOW + timedelta(minutes=5)
    app = _app(tmp_path, db_path, policy, clock, _opener(runner, finder))
    with (
        caplog.at_level(logging.INFO, logger="fairband.web"),
        TestClient(app, base_url=HOST) as client,
    ):
        found = client.get(f"/api/launches/{left}").json()
        assert (found["state"], found["stage"], found["detail"]) == ("failed", "window", STOPPED)
        assert found["updatedAt"] == clock.now.isoformat()
        assert client.get(f"/api/launches/{started}").json()["state"] == "started"
        ended = _status(client, started, {"state": "ended", "exitCode": 0})
        assert ended.status_code == 200, ended.text
    assert "1 opening launch marked failed" in caplog.messages
    assert runner.ran == []


# ------------------------------------------------------------------ the detail read


def test_the_detail_reads_item_carries_its_newest_launch(
    served: TestClient, finder: Finder
) -> None:
    """``item.launch`` is the item's newest launch as ``GET /api/launches/{id}`` answers it, and
    ``None`` with none."""
    item_id = _item(served)
    assert served.get("/api/companies/AAPL").json()["item"]["launch"] is None
    finder.missing = {"wt.exe"}
    first = _made(served, {"itemId": item_id})
    assert served.get("/api/companies/AAPL").json()["item"]["launch"] == first
    finder.missing = set()
    second = _made(served, {"itemId": item_id})
    found = served.get("/api/companies/AAPL").json()["item"]["launch"]
    assert found == second == served.get(f"/api/launches/{second['id']}").json()


def test_the_detail_reads_launch_is_read_on_the_apps_clock(
    served: TestClient, clock: Clock
) -> None:
    _made(served, {"itemId": _item(served)})
    clock.now = NOW + timedelta(seconds=90)
    found = served.get("/api/companies/AAPL").json()["item"]["launch"]
    assert (found["ageSeconds"], found["overdue"]) == (90, True)


# ------------------------------------------------------------------ serve


def test_serve_hands_the_app_an_opener_and_the_port_of_its_option(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runner: Runner, finder: Finder
) -> None:
    """``serve`` passes the app the opener of this machine, replaced here by the double, and the
    port uvicorn listens on. The window command names a program no machine has, so that even the
    real opener would find nothing to run."""
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)
    monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)
    write_launch_file(tmp_path / "xdg" / "fairband", {"window_command": "fairband-no-terminal -e"})
    answers: list[tuple[Any, httpx.Response]] = []

    def run_app(app: Any, **kwargs: Any) -> None:
        with TestClient(app, base_url=HOST) as client:
            answers.append((kwargs.get("port"), _launch(client, {"test": True})))

    monkeypatch.setattr(cli, "system_opener", lambda: _opener(runner, finder))
    monkeypatch.setattr(uvicorn, "run", run_app)
    assert cli.main(["serve", "--port", "8475"]) == 0
    ((port, answer),) = answers
    assert port == 8475
    assert answer.status_code == 201, answer.text
    launch_id = answer.json()["id"]
    added = ["bash", "-l", LAUNCHER, PYTHON, "8475", str(launch_id)]
    assert runner.ran == [["fairband-no-terminal", "-e", *added]]
