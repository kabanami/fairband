"""The launcher (spec 2026-11-16 agent launch, 6.2): ``fairband launch <port> <launch id>``, which
``launcher.sh`` runs in the window the server opened. It talks to the server on
``127.0.0.1:<port>`` alone, with a client that reads no proxy or other setting from the
environment, each call with ``X-Fairband-Request: 1`` and no principal header, so the calls are the
owner's. It reads no key and opens no database: all the logic of a launch is the server's.

In order, it:

1. reads ``GET /api/launches/{id}/command``: the agent's words and its folder;
2. makes the folder with its parents, where it is missing;
3. starts the agent as its child, from the words as a list of arguments, with no shell, in the
   folder and on the window's terminal;
4. reports ``started``;
5. ignores SIGINT while it waits for the agent, so Ctrl-C belongs to the agent, and puts the
   handler before it back after the wait. SIGINT is ignored only once the agent has started, so
   the agent does not inherit it ignored;
6. reports ``ended`` with the agent's exit code as ``Popen.wait`` gives it, a negative number for
   a signal, and answers 0, whatever that code.

Each failure writes its sentence in the window and, once the command has been read, reports
``failed`` with the same sentence; then it writes an empty line and "Press Enter to close this
window.", waits for Enter and answers 1:

- the server does not answer the command read (any transport error, a timeout among them): "no
  Fairband server answered on port <port>", reported nowhere;
- the server refuses it (any answer but a 200): its ``detail`` sentence, or "the server answered
  <status>" where its answer holds none, reported nowhere;
- the folder cannot be made: "the folder <path> cannot be made: <the error's text>";
- the program is not found: "`<program>` was not found on the path of a login shell";
- the program cannot start (any other ``OSError``): "`<program>` could not start: <the error's
  text>".

A report the server refuses or does not answer is one line in the window, "the report `<state>`
did not reach the server: <its detail sentence, or the error's kind>", and the launcher carries
on: a refused ``started`` leaves the agent running to its end.
"""

import os
import signal
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Any, TextIO

import httpx

from fairband.web.app import REQUEST_HEADER

TIMEOUT_S = 10.0
CLOSE = "Press Enter to close this window."
_HEADERS = {REQUEST_HEADER: "1"}


def run_launcher(
    port: int,
    launch_id: int,
    *,
    http: httpx.Client | None = None,
    start: Callable[[Sequence[str], str], subprocess.Popen[bytes]] | None = None,
    out: TextIO = sys.stdout,
    hold: Callable[[], None] | None = None,
) -> int:
    """Run the launch ``launch_id`` of the server on ``port`` (the module docstring): 0 after an
    agent that ran, whatever its exit code, 1 after a failure. ``http`` calls the server, a
    client of ``127.0.0.1:<port>`` by default; ``start(argv, folder)`` starts the agent,
    ``subprocess.Popen`` by default; ``out`` is the window; ``hold`` waits for Enter, a read of one
    line of the standard input by default."""
    launcher = _Launcher(launch_id, start or _start, out, hold or _wait_for_enter)
    if http is not None:
        return launcher.run(port, http)
    with _loopback(port) as client:
        return launcher.run(port, client)


class _Launcher:
    """One launch's steps, with the program start, the window and the wait for Enter."""

    def __init__(
        self,
        launch_id: int,
        start: Callable[[Sequence[str], str], subprocess.Popen[bytes]],
        out: TextIO,
        hold: Callable[[], None],
    ) -> None:
        self.launch_id = launch_id
        self.start = start
        self.out = out
        self.hold = hold

    def run(self, port: int, http: httpx.Client) -> int:
        try:
            response = http.get(f"/api/launches/{self.launch_id}/command", headers=_HEADERS)
        except httpx.TransportError:
            return self.fail(f"no Fairband server answered on port {port}")
        if response.status_code != 200:
            return self.fail(_detail(response))
        command = response.json()
        argv, folder = list(command["argv"]), command["folder"]
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            return self.fail(f"the folder {folder} cannot be made: {exc}", http)
        try:
            agent = self.start(argv, folder)
        except FileNotFoundError:
            return self.fail(f"`{argv[0]}` was not found on the path of a login shell", http)
        except OSError as exc:
            return self.fail(f"`{argv[0]}` could not start: {exc}", http)
        self.report(http, {"state": "started"})
        before = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            exit_code = agent.wait()
        finally:
            signal.signal(signal.SIGINT, signal.default_int_handler if before is None else before)
        self.report(http, {"state": "ended", "exitCode": exit_code})
        return 0

    def fail(self, sentence: str, http: httpx.Client | None = None) -> int:
        """Write ``sentence``, report it as ``failed`` through ``http`` where it is given, write
        the way out and wait for Enter; 1."""
        self.say(sentence)
        if http is not None:
            self.report(http, {"state": "failed", "detail": sentence})
        self.say("")
        self.say(CLOSE)
        self.hold()
        return 1

    def report(self, http: httpx.Client, body: dict[str, Any]) -> None:
        """Send the report ``body``; one line in the window where it does not reach the server."""
        path = f"/api/launches/{self.launch_id}/status"
        try:
            response = http.post(path, json=body, headers=_HEADERS)
        except httpx.TransportError as exc:
            reason = type(exc).__name__
        else:
            if response.status_code == 200:
                return
            reason = _detail(response)
        self.say(f"the report `{body['state']}` did not reach the server: {reason}")

    def say(self, line: str) -> None:
        self.out.write(f"{line}\n")
        self.out.flush()


def _loopback(port: int) -> httpx.Client:
    """The client of the server on 127.0.0.1:``port``: no proxy or other setting from the
    environment, and ``TIMEOUT_S``."""
    return httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=TIMEOUT_S, trust_env=False)


def _start(argv: Sequence[str], folder: str) -> subprocess.Popen[bytes]:
    """Start ``argv`` as a list of arguments, with no shell, in ``folder``; its input and output are
    the launcher's, the window's terminal."""
    return subprocess.Popen(list(argv), cwd=folder, shell=False)


def _wait_for_enter() -> None:
    """Read one line of the standard input; return at its end as well."""
    try:
        input()
    except EOFError:
        return


def _detail(response: httpx.Response) -> str:
    """The ``detail`` sentence of a refusal's JSON, or "the server answered <status>" where it
    holds none."""
    try:
        answer = response.json()
    except ValueError:  # not JSON
        answer = None
    detail = answer.get("detail") if isinstance(answer, dict) else None
    if isinstance(detail, str) and detail.strip():
        return detail
    return f"the server answered {response.status_code}"
