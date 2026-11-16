"""The launcher against the launch routes, end to end (spec 2026-11-16 agent launch, 6): the real
app, whose opener is a double that records the window command's words and runs nothing, and the
real ``run_launcher``, whose client is a ``TestClient`` of that app (an ``httpx.Client``) and whose
program start is a double, so no window opens, no agent starts and no network is used. The
launcher takes its port and its launch's id from the words the window command was given, as the
script in the window does."""

import subprocess
from collections.abc import Iterator, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.web import HEADER, HOST, NOW, _settings

from fairband.launch.command import Opener
from fairband.launch.run import run_launcher
from fairband.launch.settings import write_launch_file
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.web.app import create_app
from fairband.web.identity import ACTOR_HEADER, PRINCIPAL_HEADER

AGENT = "claude-opus-5-5"
AS_AGENT = HEADER | {PRINCIPAL_HEADER: "agent", ACTOR_HEADER: AGENT}
WT_LINE = "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e"
LAUNCHER = "/pkg/fairband/launch/launcher.sh"
PYTHON = "/usr/bin/python3"
PORT = 8470
CLOSE = "Press Enter to close this window."


class Runner:
    """The window command's runner: it records each list of words and answers exit 0, running
    nothing."""

    def __init__(self) -> None:
        self.ran: list[list[str]] = []

    def __call__(self, words: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
        self.ran.append(list(words))
        return subprocess.CompletedProcess(list(words), 0, None, b"")


class Agent:
    """A started Claude Code: while the launcher waits for it, it reads its launch, claims its
    item as the agent ``AGENT`` and ends with exit code 0."""

    def __init__(self, client: TestClient, launch_id: int, item_id: int) -> None:
        self.client = client
        self.launch_id = launch_id
        self.item_id = item_id
        self.launch_while_running: dict[str, Any] = {}

    def wait(self) -> int:
        self.launch_while_running = self.client.get(f"/api/launches/{self.launch_id}").json()
        claimed = self.client.post(
            "/api/inbox/claim", json={"itemId": self.item_id}, headers=AS_AGENT
        )
        assert claimed.status_code == 200, claimed.text
        return 0


class Start:
    """The launcher's program start: it records each argv and folder, then answers ``agent`` or
    raises ``raises``."""

    def __init__(self, agent: Agent | None = None, raises: OSError | None = None) -> None:
        self.agent = agent
        self.raises = raises
        self.started: list[tuple[list[str], str]] = []

    def __call__(self, argv: Sequence[str], folder: str) -> Any:
        self.started.append((list(argv), folder))
        if self.raises is not None:
            raise self.raises
        return self.agent


class Hold:
    """The wait for Enter: it counts its calls."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


@pytest.fixture
def runner() -> Runner:
    return Runner()


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """The agent's folder, which the launcher makes."""
    return tmp_path / "research" / "fairband"


@pytest.fixture
def client(
    tmp_path: Path, db_path: Path, policy: Policy, runner: Runner, folder: Path
) -> Iterator[TestClient]:
    """A client of an app on port 8470 with the double opener, whose launch file is the founder's
    line with every field of Claude Code's set and the folder ``folder``."""
    settings = _settings(tmp_path, db_path)
    write_launch_file(
        settings.config_dir,
        {
            "window_command": WT_LINE,
            "claude.model": AGENT,
            "claude.effort": "xhigh",
            "claude.permission_mode": "auto",
            "claude.folder": str(folder),
        },
    )
    opener = Opener(
        run=runner,
        which=lambda program: f"/found/{program}",
        python=PYTHON,
        launcher=LAUNCHER,
        environ={},
    )
    app = create_app(
        settings, policy, lambda: connect(db_path), clock=lambda: NOW, opener=opener, port=PORT
    )
    with TestClient(app, base_url=HOST) as served:
        yield served


def _launched(client: TestClient, runner: Runner) -> tuple[int, int, int]:
    """A pending item for AAPL and its launch, the window's words recorded: the item's id, and the
    port and launch id the window's launcher is given, its two last words."""
    posted = client.post(
        "/api/inbox", json={"symbol": "AAPL", "mode": "full report", "note": ""}, headers=HEADER
    )
    assert posted.status_code == 201, posted.text
    item_id: int = posted.json()["id"]
    launched = client.post("/api/launches", json={"itemId": item_id}, headers=HEADER)
    assert launched.status_code == 201, launched.text
    assert launched.json()["state"] == "opened"
    [words] = runner.ran
    assert words[-6:-2] == ["bash", "-l", LAUNCHER, PYTHON]
    port, launch_id = int(words[-2]), int(words[-1])
    assert (port, launch_id) == (PORT, launched.json()["id"])
    return item_id, port, launch_id


def test_a_launch_runs_from_the_window_to_the_claim_and_the_agents_end(
    client: TestClient, runner: Runner, folder: Path
) -> None:
    """The launcher reads its launch's command and gets the agent's words and folder, makes the
    folder, starts the agent and reports ``started``; the agent claims the item while it runs;
    the launcher reports ``ended``, and the launch's read then says ``ended`` with the item
    claimed."""
    item_id, port, launch_id = _launched(client, runner)
    agent = Agent(client, launch_id, item_id)
    start, out, hold = Start(agent), StringIO(), Hold()

    assert run_launcher(port, launch_id, http=client, start=start, out=out, hold=hold) == 0

    words = [
        "claude",
        "--model",
        AGENT,
        "--effort",
        "xhigh",
        "--permission-mode",
        "auto",
        f"/fairband-research work item {item_id}",
    ]
    assert start.started == [(words, str(folder))]
    assert folder.is_dir()
    running = agent.launch_while_running
    assert (running["state"], running["itemState"]) == ("started", "pending")
    assert (out.getvalue(), hold.calls) == ("", 0)
    read = client.get(f"/api/launches/{launch_id}").json()
    assert {name: read[name] for name in ("state", "exitCode", "itemState", "claimedBy")} == {
        "state": "ended",
        "exitCode": 0,
        "itemState": "claimed",
        "claimedBy": AGENT,
    }
    assert read["overdue"] is False


def test_an_agent_program_not_found_fails_the_launch_at_the_agent_stage(
    client: TestClient, runner: Runner
) -> None:
    """The program is not found on the login shell's path: the launcher writes the sentence,
    reports it, and holds the window; the launch's read says ``failed`` at the ``agent`` stage
    with that sentence, and the item is still pending."""
    _, port, launch_id = _launched(client, runner)
    start = Start(raises=FileNotFoundError(2, "No such file or directory", "claude"))
    out, hold = StringIO(), Hold()

    assert run_launcher(port, launch_id, http=client, start=start, out=out, hold=hold) == 1

    sentence = "`claude` was not found on the path of a login shell"
    assert out.getvalue() == f"{sentence}\n\n{CLOSE}\n"
    assert hold.calls == 1
    read = client.get(f"/api/launches/{launch_id}").json()
    assert {name: read[name] for name in ("state", "stage", "detail", "itemState")} == {
        "state": "failed",
        "stage": "agent",
        "detail": sentence,
        "itemState": "pending",
    }
