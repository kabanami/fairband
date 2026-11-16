"""The words of a launch (spec 2026-11-16 agent launch, 6.1 and 6.3): the window command that
opens a terminal window, its run and the sentence of each way it fails, and the agent's words, the
Claude Code command the launcher starts in that window.

Only plain words cross the window (spec 5): Windows Terminal splits a word that holds a space into
several, quoted or not. A plain word is one or more of letters, digits and ``_ . / : @ + -``.
``window_words`` adds six words to the window command, ``bash -l``, the launcher script's path,
the server's Python, its port and the launch id, and refuses a title or one of the last four words
that is not plain before anything runs. The prompt holds spaces, so it is no word of the window
command: it is the last of the agent's words, which the launcher reads from the server and starts
as a list of arguments, with no shell.

``Opener`` holds what opening a window reaches outside the server: the runner of the window
command, the program finder, the server's Python, the launcher script's path and the server's
environment. ``system_opener`` answers the real ones; the tests pass doubles.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import resources

from fairband.store.inbox import WorkItem

WINDOW_LIMIT_S = 15
TEST_PROMPT = "/fairband-research launch test"

_PLAIN = re.compile(r"[A-Za-z0-9_./:@+-]+")
_LINE_LIMIT = 200
# The options of Claude Code 2.1.325 that the Agents section sets, in the order they are added.
_OPTIONS = (
    ("claude.model", "--model"),
    ("claude.effort", "--effort"),
    ("claude.permission_mode", "--permission-mode"),
)


class WindowFailed(Exception):
    """The window command failed, or would have: ``str(exc)`` is the failure's sentence."""


@dataclass(frozen=True)
class Opener:
    """What opening a window reaches outside the server. ``run`` runs a list of words and answers
    how the program ended; ``which`` answers a program's path, or ``None`` where it finds none;
    ``python`` and ``launcher`` are the paths the window's program starts from; ``environ`` is the
    server's environment."""

    run: Callable[[Sequence[str]], subprocess.CompletedProcess[bytes]]
    which: Callable[[str], str | None]
    python: str
    launcher: str
    environ: Mapping[str, str]


def system_opener() -> Opener:
    """The opener of a running server: ``subprocess`` with no shell, ``shutil.which``, this
    Python, the packaged ``launcher.sh`` and ``os.environ``."""
    return Opener(
        run=_run,
        which=shutil.which,
        python=sys.executable,
        launcher=str(resources.files("fairband.launch").joinpath("launcher.sh")),
        environ=os.environ,
    )


def is_plain(word: str) -> bool:
    """``word`` is one or more of letters, digits and ``_ . / : @ + -``, so it crosses the window
    whole."""
    return _PLAIN.fullmatch(word) is not None


def window_words(
    window_command: str, title: str, opener: Opener, port: int, launch_id: int
) -> list[str]:
    """The words the server runs to open the window: ``window_command`` split by the shell's
    rules, with ``{title}`` replaced by ``title`` in each word, then ``bash``, ``-l``, the launcher
    script's path, the server's Python, ``port`` and ``launch_id``. A title or one of the last four
    words that is not plain is ``WindowFailed``, before anything runs."""
    added = [opener.launcher, opener.python, str(port), str(launch_id)]
    for word in [title, *added]:
        if not is_plain(word):
            raise WindowFailed(
                f"`{word}` cannot cross the window: it holds a character other than letters, "
                "digits and _ . / : @ + -"
            )
    words = [word.replace("{title}", title) for word in shlex.split(window_command)]
    return [*words, "bash", "-l", *added]


def open_window(words: Sequence[str], opener: Opener) -> None:
    """Run ``words`` through ``opener`` as a list of arguments. Where the first word is not a
    program ``opener.which`` finds, nothing runs. Each failure is ``WindowFailed`` with its
    sentence: the program was not found, it could not start, it did not end within
    ``WINDOW_LIMIT_S`` seconds, or it ended with an exit code other than 0, with the first line of
    its error output that holds text."""
    program = words[0]
    if opener.which(program) is None:
        raise WindowFailed(f"`{program}` was not found")
    try:
        ended = opener.run(list(words))
    except FileNotFoundError:
        raise WindowFailed(f"`{program}` was not found") from None
    except OSError as error:
        raise WindowFailed(f"the window command could not start: {error}") from None
    except subprocess.TimeoutExpired:
        raise WindowFailed(f"the window command did not end in {WINDOW_LIMIT_S} seconds") from None
    if ended.returncode != 0:
        sentence = f"the window command ended with exit code {ended.returncode}"
        line = _first_line(ended.stderr)
        raise WindowFailed(f"{sentence}: {line}" if line else sentence)


def agent_words(values: Mapping[str, str], item: WorkItem | None) -> list[str]:
    """The words the launcher starts in the window, from the launch file's ``values``: the Claude
    Code command split by the shell's rules, ``--model``, ``--effort`` and ``--permission-mode``
    each with its value where that is set, and the first prompt as one last word: the prompt with
    ``{item}``, ``{symbol}`` and ``{mode}`` replaced from ``item``, or ``TEST_PROMPT`` for a test,
    which has no item."""
    words = shlex.split(values["claude.command"])
    for name, option in _OPTIONS:
        if values[name]:
            words += [option, values[name]]
    if item is None:
        return [*words, TEST_PROMPT]
    prompt = (
        values["claude.prompt"]
        .replace("{item}", str(item.id))
        .replace("{symbol}", item.symbol)
        .replace("{mode}", item.mode)
    )
    return [*words, prompt]


def title_of(item: WorkItem | None) -> str:
    """The window's title: ``Fairband-`` and the item's symbol, or ``Fairband-test`` for a test."""
    return "Fairband-test" if item is None else f"Fairband-{item.symbol}"


def _run(words: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    """Run ``words`` as a list of arguments, with no shell, the input closed and the output
    captured, in the server's folder and environment; after ``WINDOW_LIMIT_S`` seconds the program
    is killed and ``subprocess.TimeoutExpired`` raised."""
    return subprocess.run(
        list(words),
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=WINDOW_LIMIT_S,
        check=False,
    )


def _first_line(error_output: bytes) -> str:
    """The first line of ``error_output`` that holds text, stripped and cut to 200 characters; an
    empty string where no line holds text. NUL bytes are dropped first, so the UTF-16 a Windows
    program writes reads as its text; the rest decodes as UTF-8, a byte that is not UTF-8 read as
    the replacement character."""
    text = error_output.replace(b"\0", b"").decode("utf-8", errors="replace")
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:_LINE_LIMIT]
    return ""
