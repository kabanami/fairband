"""The launcher (spec 2026-11-16 agent launch, 6.2): ``fairband launch <port> <launch id>`` reads
the agent's words and folder from the server, makes the folder, starts the agent as its child,
reports ``started``, waits with Ctrl-C left to the agent, and reports ``ended``. Each failure is
written in the window, reported where it can be, and held until Enter; a report that does not
reach the server is one line and stops nothing.

The server is an ``httpx.MockTransport`` and the program start a double, so no test starts an agent
or uses the network. One test starts this Python itself through the default start."""

import json
import signal
import sys
from collections.abc import Callable, Iterator, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import httpx
import pytest

from fairband.launch import run
from fairband.launch.run import run_launcher
from fairband.web.app import REQUEST_HEADER
from fairband.web.identity import PRINCIPAL_HEADER

PORT = 8470
LAUNCH = 17
COMMAND = f"/api/launches/{LAUNCH}/command"
STATUS = f"/api/launches/{LAUNCH}/status"
ARGV = ["claude", "--model", "claude-opus-5-5", "/fairband-research work item 12"]
CLOSE = "Press Enter to close this window."
CLAIMED = "item 12 is claimed by claude-opus-5-5"


class Server:
    """The server's two launcher routes. The command read answers ``command``, a status and a
    body, or raises ``down``; a report of a state answers ``refused[state]`` or raises
    ``dropped[state]``, else 200. Every request is recorded, with SIGINT's handler as it came."""

    def __init__(self, folder: Path) -> None:
        self.command: tuple[int, Any] = (200, {"argv": ARGV, "folder": str(folder)})
        self.down: httpx.TransportError | None = None
        self.refused: dict[str, tuple[int, Any]] = {}
        self.dropped: dict[str, Exception] = {}
        self.requests: list[httpx.Request] = []
        self.sigint: list[Any] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.sigint.append(signal.getsignal(signal.SIGINT))
        if request.url.path == COMMAND:
            if self.down is not None:
                raise self.down
            status, body = self.command
            return httpx.Response(status, json=body)
        state = json.loads(request.content)["state"]
        if state in self.dropped:
            raise self.dropped[state]
        status, body = self.refused.get(state, (200, {"id": LAUNCH, "state": state}))
        return httpx.Response(status, json=body)

    @property
    def calls(self) -> list[tuple[str, str, Any]]:
        """Each request's method, path and JSON body (``None`` for none)."""
        return [
            (r.method, r.url.path, json.loads(r.content) if r.content else None)
            for r in self.requests
        ]


class Agent:
    """A started agent: ``wait`` notes SIGINT's handler and the requests made so far, then
    answers ``code`` or raises ``raises``."""

    def __init__(self, server: Server, code: int = 3, raises: Exception | None = None) -> None:
        self.server = server
        self.code = code
        self.raises = raises
        self.waited = False
        self.sigint_while_waiting: Any = None
        self.requests_before_wait = -1

    def wait(self) -> int:
        self.waited = True
        self.sigint_while_waiting = signal.getsignal(signal.SIGINT)
        self.requests_before_wait = len(self.server.requests)
        if self.raises is not None:
            raise self.raises
        return self.code


class Start:
    """The program start: it records each argv and folder, whether the folder was there, SIGINT's
    handler and the requests made so far, then answers ``agent`` or raises ``raises``."""

    def __init__(self, agent: Agent, raises: OSError | None = None) -> None:
        self.agent = agent
        self.raises = raises
        self.started: list[tuple[Any, str]] = []
        self.folder_was_there = False
        self.sigint_at_start: Any = None
        self.requests_before_start = -1

    def __call__(self, argv: Sequence[str], folder: str) -> Any:
        self.started.append((argv, folder))
        self.folder_was_there = Path(folder).is_dir()
        self.sigint_at_start = signal.getsignal(signal.SIGINT)
        self.requests_before_start = len(self.agent.server.requests)
        if self.raises is not None:
            raise self.raises
        return self.agent


class Hold:
    """The wait for Enter: it counts its calls and keeps what the window showed at each and the
    requests the server had by then."""

    def __init__(self, out: StringIO, server: Server) -> None:
        self.out = out
        self.server = server
        self.shown: list[str] = []
        self.requests_before: list[int] = []

    def __call__(self) -> None:
        self.shown.append(self.out.getvalue())
        self.requests_before.append(len(self.server.requests))


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """The agent's folder, two levels below a folder that is there."""
    return tmp_path / "home" / "fairband-research"


@pytest.fixture
def server(folder: Path) -> Server:
    return Server(folder)


@pytest.fixture
def http(server: Server) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(server), base_url=f"http://127.0.0.1:{PORT}")


@pytest.fixture
def out() -> StringIO:
    return StringIO()


@pytest.fixture
def hold(out: StringIO, server: Server) -> Hold:
    return Hold(out, server)


@pytest.fixture
def earlier() -> Iterator[Callable[[int, Any], None]]:
    """A SIGINT handler of the launcher's caller, in place for the test and taken out after it."""

    def handler(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt

    before = signal.signal(signal.SIGINT, handler)
    yield handler
    signal.signal(signal.SIGINT, before)


@pytest.fixture
def agent(server: Server) -> Agent:
    return Agent(server)


@pytest.fixture
def start(agent: Agent) -> Start:
    return Start(agent)


def _run(http: httpx.Client, start: Start, out: StringIO, hold: Hold) -> int:
    return run_launcher(PORT, LAUNCH, http=http, start=start, out=out, hold=hold)


def _window(*lines: str) -> str:
    """What a failure leaves in the window: its lines, an empty line and the way out."""
    return "".join(f"{line}\n" for line in (*lines, "", CLOSE))


def _ended(code: int) -> str:
    """What an agent that ended with ``code``, not 0, leaves in the window."""
    return _window(f"Claude Code ended with exit code {code}.")


def test_a_launch_reads_the_command_starts_the_agent_and_reports_its_end(
    http: httpx.Client, server: Server, start: Start, out: StringIO, hold: Hold, folder: Path
) -> None:
    assert _run(http, start, out, hold) == 0
    assert server.calls == [
        ("GET", COMMAND, None),
        ("POST", STATUS, {"state": "started"}),
        ("POST", STATUS, {"state": "ended", "exitCode": 3}),
    ]
    for request in server.requests:
        assert request.headers.get(REQUEST_HEADER) == "1"
        assert PRINCIPAL_HEADER not in request.headers
    assert folder.is_dir()
    assert start.started == [(ARGV, str(folder))]
    assert isinstance(start.started[0][0], list), "the agent starts from a list of arguments"
    assert start.folder_was_there, "the folder is made before the agent starts"
    assert out.getvalue() == _ended(3)
    assert hold.shown == [_ended(3)]


@pytest.mark.parametrize("code", [3, 1, -2])
def test_an_agent_that_ends_with_another_code_than_0_is_written_and_held_after_its_report(
    http: httpx.Client,
    server: Server,
    agent: Agent,
    start: Start,
    out: StringIO,
    hold: Hold,
    code: int,
) -> None:
    """Claude Code's own error line (a refused option, an unknown model) is on the window's
    screen; a window that closed on the launcher's 0 would take it away."""
    agent.code = code
    assert _run(http, start, out, hold) == 0
    assert out.getvalue() == _ended(code)
    assert hold.shown == [_ended(code)]
    assert hold.requests_before == [3], "held after the ended report"
    assert server.calls[-1] == ("POST", STATUS, {"state": "ended", "exitCode": code})


def test_an_agent_that_ends_with_0_writes_nothing_and_is_not_held(
    http: httpx.Client, server: Server, agent: Agent, start: Start, out: StringIO, hold: Hold
) -> None:
    agent.code = 0
    assert _run(http, start, out, hold) == 0
    assert out.getvalue() == ""
    assert hold.shown == []
    assert server.calls[-1] == ("POST", STATUS, {"state": "ended", "exitCode": 0})


def test_started_is_reported_after_the_agent_has_started_and_before_the_wait(
    http: httpx.Client, start: Start, agent: Agent, out: StringIO, hold: Hold
) -> None:
    _run(http, start, out, hold)
    assert start.requests_before_start == 1  # the command read alone
    assert agent.requests_before_wait == 2  # the command read and started


@pytest.mark.parametrize("code", [0, 1, -2])
def test_the_answer_is_0_after_an_agent_that_ran_whatever_its_exit_code(
    http: httpx.Client,
    server: Server,
    agent: Agent,
    start: Start,
    out: StringIO,
    hold: Hold,
    code: int,
) -> None:
    agent.code = code  # -2: ended by SIGINT, as Popen.wait() gives it
    assert _run(http, start, out, hold) == 0
    assert server.calls[-1] == ("POST", STATUS, {"state": "ended", "exitCode": code})


def test_ctrl_c_belongs_to_the_agent_while_the_launcher_waits(
    http: httpx.Client, start: Start, agent: Agent, out: StringIO, hold: Hold
) -> None:
    before = signal.getsignal(signal.SIGINT)
    assert before is signal.default_int_handler
    _run(http, start, out, hold)
    assert start.sigint_at_start is before, "the agent does not inherit an ignored SIGINT"
    assert agent.sigint_while_waiting is signal.SIG_IGN
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def test_sigint_is_restored_when_the_wait_raises(
    http: httpx.Client, start: Start, agent: Agent, out: StringIO, hold: Hold
) -> None:
    agent.raises = RuntimeError("the wait broke")
    with pytest.raises(RuntimeError):
        _run(http, start, out, hold)
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def test_sigint_is_ignored_from_the_agents_start_and_the_earlier_handler_is_put_back(
    http: httpx.Client,
    server: Server,
    start: Start,
    agent: Agent,
    out: StringIO,
    hold: Hold,
    earlier: Callable[[int, Any], None],
) -> None:
    """A Ctrl-C meant for the agent while the started report is in flight does not end the
    launcher: SIGINT is ignored once the agent has started, before the report."""
    assert _run(http, start, out, hold) == 0
    assert start.sigint_at_start is earlier, "the agent does not inherit an ignored SIGINT"
    assert server.sigint == [earlier, signal.SIG_IGN, earlier]
    assert agent.sigint_while_waiting is signal.SIG_IGN
    assert signal.getsignal(signal.SIGINT) is earlier


@pytest.mark.parametrize("where", ["report", "wait"])
def test_the_earlier_sigint_handler_is_put_back_when_the_report_or_the_wait_raises(
    http: httpx.Client,
    server: Server,
    start: Start,
    agent: Agent,
    out: StringIO,
    hold: Hold,
    earlier: Callable[[int, Any], None],
    where: str,
) -> None:
    if where == "report":
        server.dropped["started"] = RuntimeError("the report broke")
    else:
        agent.raises = RuntimeError("the wait broke")
    with pytest.raises(RuntimeError, match=f"^the {where} broke$"):
        _run(http, start, out, hold)
    assert server.sigint[1] is signal.SIG_IGN
    assert signal.getsignal(signal.SIGINT) is earlier


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("Connection refused"), httpx.ReadTimeout("timed out")]
)
def test_a_server_that_does_not_answer_is_written_and_held(
    http: httpx.Client,
    server: Server,
    start: Start,
    out: StringIO,
    hold: Hold,
    error: httpx.TransportError,
) -> None:
    server.down = error
    assert _run(http, start, out, hold) == 1
    window = _window("no Fairband server answered on port 8470")
    assert out.getvalue() == window
    assert hold.shown == [window]
    assert server.calls == [("GET", COMMAND, None)]
    assert start.started == []


def test_a_refused_command_read_writes_the_servers_sentence_and_reports_nothing(
    http: httpx.Client, server: Server, start: Start, out: StringIO, hold: Hold, folder: Path
) -> None:
    server.command = (409, {"detail": CLAIMED})
    assert _run(http, start, out, hold) == 1
    assert out.getvalue() == _window(CLAIMED)
    assert hold.shown == [_window(CLAIMED)]
    assert server.calls == [("GET", COMMAND, None)]
    assert start.started == []
    assert not folder.exists()


def test_a_refusal_with_no_sentence_names_its_status(
    http: httpx.Client, server: Server, start: Start, out: StringIO, hold: Hold
) -> None:
    server.command = (500, "Internal Server Error")
    assert _run(http, start, out, hold) == 1
    assert out.getvalue() == _window("the server answered 500")
    assert len(hold.shown) == 1


def test_a_folder_that_cannot_be_made_is_written_reported_and_held(
    http: httpx.Client, server: Server, start: Start, out: StringIO, hold: Hold, tmp_path: Path
) -> None:
    (tmp_path / "file").write_text("not a folder", encoding="utf-8")
    folder = tmp_path / "file" / "fairband-research"
    server.command = (200, {"argv": ARGV, "folder": str(folder)})
    sentence = f"the folder {folder} cannot be made: [Errno 20] Not a directory: '{folder}'"
    assert _run(http, start, out, hold) == 1
    assert out.getvalue() == _window(sentence)
    assert hold.shown == [_window(sentence)]
    assert server.calls == [
        ("GET", COMMAND, None),
        ("POST", STATUS, {"state": "failed", "detail": sentence}),
    ]
    assert start.started == []


def test_a_program_not_found_is_written_reported_and_held(
    http: httpx.Client, server: Server, start: Start, out: StringIO, hold: Hold
) -> None:
    start.raises = FileNotFoundError(2, "No such file or directory", "claude")
    sentence = "`claude` was not found on the path of a login shell"
    assert _run(http, start, out, hold) == 1
    assert out.getvalue() == _window(sentence)
    assert hold.shown == [_window(sentence)]
    assert server.calls == [
        ("GET", COMMAND, None),
        ("POST", STATUS, {"state": "failed", "detail": sentence}),
    ]
    assert len(start.started) == 1


def test_a_program_that_cannot_start_is_written_reported_and_held(
    http: httpx.Client, server: Server, start: Start, out: StringIO, hold: Hold
) -> None:
    start.raises = PermissionError(13, "Permission denied", "claude")
    sentence = "`claude` could not start: [Errno 13] Permission denied: 'claude'"
    assert _run(http, start, out, hold) == 1
    assert out.getvalue() == _window(sentence)
    assert hold.shown == [_window(sentence)]
    assert server.calls == [
        ("GET", COMMAND, None),
        ("POST", STATUS, {"state": "failed", "detail": sentence}),
    ]


def test_a_refused_started_report_leaves_the_agent_running_to_its_end(
    http: httpx.Client, server: Server, start: Start, agent: Agent, out: StringIO, hold: Hold
) -> None:
    refusal = "a launch that is failed does not become started"
    server.refused["started"] = (409, {"detail": refusal})
    assert _run(http, start, out, hold) == 0
    assert agent.waited
    unreported = f"the report `started` did not reach the server: {refusal}\n"
    assert out.getvalue() == unreported + _ended(3)
    assert server.calls[-1] == ("POST", STATUS, {"state": "ended", "exitCode": 3})
    assert hold.shown == [unreported + _ended(3)]


def test_an_ended_report_the_server_does_not_answer_is_one_line(
    http: httpx.Client, server: Server, agent: Agent, start: Start, out: StringIO, hold: Hold
) -> None:
    server.dropped["ended"] = httpx.ConnectError("Connection refused")
    assert _run(http, start, out, hold) == 0
    unreported = "the report `ended` did not reach the server: ConnectError\n"
    assert out.getvalue() == unreported + _ended(3)
    assert hold.shown == [unreported + _ended(3)]
    agent.code = 0
    out.seek(0)
    out.truncate()
    assert _run(http, start, out, hold) == 0
    assert out.getvalue() == unreported
    assert len(hold.shown) == 1


def test_a_refused_failed_report_is_written_before_the_way_out(
    http: httpx.Client, server: Server, start: Start, out: StringIO, hold: Hold
) -> None:
    start.raises = FileNotFoundError(2, "No such file or directory", "claude")
    server.refused["failed"] = (404, {"detail": f"no launch {LAUNCH}"})
    sentence = "`claude` was not found on the path of a login shell"
    unreported = f"the report `failed` did not reach the server: no launch {LAUNCH}"
    assert _run(http, start, out, hold) == 1
    assert out.getvalue() == _window(sentence, unreported)
    assert hold.shown == [_window(sentence, unreported)]


def test_the_default_start_runs_the_words_in_the_folder_and_reports_the_exit_code(
    http: httpx.Client, server: Server, out: StringIO, hold: Hold, folder: Path
) -> None:
    # This Python, not an agent: it marks the folder it runs in and ends with exit code 3.
    argv = [
        sys.executable,
        "-c",
        "import pathlib; pathlib.Path('ran').touch(); raise SystemExit(3)",
    ]
    server.command = (200, {"argv": argv, "folder": str(folder)})
    assert run_launcher(PORT, LAUNCH, http=http, out=out, hold=hold) == 0
    assert (folder / "ran").is_file()
    assert server.calls[-1] == ("POST", STATUS, {"state": "ended", "exitCode": 3})
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def test_the_default_hold_returns_at_the_end_of_the_input(
    http: httpx.Client,
    server: Server,
    start: Start,
    out: StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    server.command = (409, {"detail": CLAIMED})
    assert run_launcher(PORT, LAUNCH, http=http, start=start, out=out) == 1
    assert out.getvalue() == _window(CLAIMED)


class _Interrupted(StringIO):
    """A standard input at which the reader presses Ctrl-C."""

    def readline(self, size: int | None = -1) -> str:
        raise KeyboardInterrupt


def test_the_default_hold_returns_quietly_on_ctrl_c(
    http: httpx.Client,
    server: Server,
    start: Start,
    out: StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", _Interrupted())
    server.command = (409, {"detail": CLAIMED})
    assert run_launcher(PORT, LAUNCH, http=http, start=start, out=out) == 1
    assert out.getvalue() == _window(CLAIMED)


def test_the_default_hold_reads_one_line(
    http: httpx.Client,
    server: Server,
    start: Start,
    out: StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdin = StringIO("\nthe next line\n")
    monkeypatch.setattr(sys, "stdin", stdin)
    server.command = (409, {"detail": CLAIMED})
    assert run_launcher(PORT, LAUNCH, http=http, start=start, out=out) == 1
    assert stdin.read() == "the next line\n"


def test_the_default_client_calls_the_port_on_the_loopback_and_reads_no_environment() -> None:
    with run._loopback(9000) as client:
        assert str(client.base_url) == "http://127.0.0.1:9000"
        assert client.trust_env is False
        assert client.timeout == httpx.Timeout(10.0)


def test_the_launcher_reads_no_key_and_opens_no_database() -> None:
    source = Path(run.__file__).read_text(encoding="utf-8")
    for name in ("fairband.store", "load_keys", "sqlite3"):
        assert name not in source
