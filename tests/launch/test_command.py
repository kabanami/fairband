"""The words of a launch (spec 2026-11-16 agent launch, 6.1 to 6.3): a plain word, the window
command's words, the window command's run and its failures' sentences, the agent's words and the
launcher script. The window command's runner and the program finder are doubles; the system
runner runs this Python only, so no test opens a window or starts an agent."""

import os
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

import pytest

from fairband.launch.command import (
    TEST_PROMPT,
    WINDOW_LIMIT_S,
    Opener,
    WindowFailed,
    agent_words,
    is_plain,
    open_window,
    system_opener,
    title_of,
    window_words,
)
from fairband.store.inbox import Mode, WorkItem

# The window command of spec 6.1, on the founder's machine.
LINE = "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e"
LAUNCHER = "/home/u/.venv/lib/python3.13/site-packages/fairband/launch/launcher.sh"
PYTHON = "/home/u/.venv/bin/python"
CROSS = "cannot cross the window: it holds a character other than letters, digits and _ . / : @ + -"
# Every field of the Agents section set, as in spec 7.2's example.
VALUES = {
    "window_command": LINE,
    "claude.command": "claude",
    "claude.prompt": "/fairband-research work item {item}",
    "claude.model": "claude-opus-5-5",
    "claude.effort": "xhigh",
    "claude.permission_mode": "auto",
    "claude.folder": "~/fairband-research",
}
NONE_SET = VALUES | {"claude.model": "", "claude.effort": "", "claude.permission_mode": ""}


def _item(item_id: int, symbol: str, mode: Mode) -> WorkItem:
    return WorkItem(
        id=item_id,
        symbol=symbol,
        mode=mode,
        note="",
        snapshot_id=None,
        origin="owner",
        posted_by="owner",
        posted_actor=None,
        posted_client=None,
        posted_at=datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
        state="pending",
        claimed_by=None,
        claimed_at=None,
        report_id=None,
        reason=None,
        finished_at=None,
        expiry_valid_until=None,
    )


QCOM = _item(12, "QCOM", "full report")
AAPL = _item(3, "AAPL", "valuation review")


class _Runner:
    """A window command's runner that records the words it is given and answers ``answer``, or
    raises it."""

    def __init__(self, answer: subprocess.CompletedProcess[bytes] | BaseException) -> None:
        self.answer = answer
        self.calls: list[Sequence[str]] = []

    def __call__(self, words: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(words)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


class _Finder:
    """A program finder that finds ``programs`` and records what it was asked."""

    def __init__(self, *programs: str) -> None:
        self.programs = programs
        self.asked: list[str] = []

    def __call__(self, program: str) -> str | None:
        self.asked.append(program)
        return f"/mnt/c/Windows/{program}" if program in self.programs else None


def _ended(code: int, error_output: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=b"", stderr=error_output)


def _opener(
    runner: _Runner | None = None,
    finder: _Finder | None = None,
    launcher: str = LAUNCHER,
    python: str = PYTHON,
) -> Opener:
    return Opener(
        run=runner if runner is not None else _Runner(_ended(0)),
        which=finder if finder is not None else _Finder("wt.exe"),
        python=python,
        launcher=launcher,
        environ={"WSL_DISTRO_NAME": "Ubuntu"},
    )


def _failure(words: Sequence[str], opener: Opener) -> str:
    with pytest.raises(WindowFailed) as failed:
        open_window(words, opener)
    return str(failed.value)


# A plain word.


@pytest.mark.parametrize(
    "word",
    [PYTHON, "BRK.B", "BF-B", "Fairband-AAPL", "8470", "user@host:/x+y_z", "-l"],
)
def test_a_plain_word(word: str) -> None:
    assert is_plain(word)


@pytest.mark.parametrize(
    "word",
    ["/home/my user/launcher.sh", "it's", 'say "hi"', "a;b", "$HOME", "", "AAPL\n", "a\tb"],
)
def test_a_word_that_is_not_plain(word: str) -> None:
    assert not is_plain(word)


# The window command's words.


def test_the_title_of_an_item_and_of_a_test() -> None:
    assert title_of(AAPL) == "Fairband-AAPL"
    assert title_of(QCOM) == "Fairband-QCOM"
    assert title_of(None) == "Fairband-test"


def test_the_window_words_of_spec_6_1() -> None:
    words = window_words(LINE, title_of(AAPL), _opener(), 8470, 17)
    assert words == [
        "wt.exe",
        "-w",
        "0",
        "new-tab",
        "--title",
        "Fairband-AAPL",
        "wsl.exe",
        "-d",
        "Ubuntu",
        "-e",
        "bash",
        "-l",
        LAUNCHER,
        PYTHON,
        "8470",
        "17",
    ]


def test_the_title_is_replaced_in_every_word_and_another_brace_stays() -> None:
    line = "term '--name={title}' --tab {title}{title} {other} {"
    words = window_words(line, "Fairband-test", _opener(), 9000, 1)
    assert words[:6] == [
        "term",
        "--name=Fairband-test",
        "--tab",
        "Fairband-testFairband-test",
        "{other}",
        "{",
    ]


def test_a_window_command_of_quoted_words_splits_by_the_shells_rules() -> None:
    line = "'/mnt/c/Program Files/term.exe' --title \"{title}\" -e"
    words = window_words(line, "Fairband-QCOM", _opener(), 8470, 2)
    assert words[:4] == ["/mnt/c/Program Files/term.exe", "--title", "Fairband-QCOM", "-e"]


@pytest.mark.parametrize(
    ("launcher", "python", "named"),
    [
        ("/home/my user/launcher.sh", PYTHON, "/home/my user/launcher.sh"),
        (LAUNCHER, "/home/my user/.venv/bin/python", "/home/my user/.venv/bin/python"),
    ],
)
def test_a_path_with_a_space_fails_before_anything_runs(
    launcher: str, python: str, named: str
) -> None:
    runner = _Runner(_ended(0))
    finder = _Finder("wt.exe")
    opener = _opener(runner, finder, launcher=launcher, python=python)
    with pytest.raises(WindowFailed) as failed:
        window_words(LINE, "Fairband-AAPL", opener, 8470, 17)
    assert str(failed.value) == f"`{named}` {CROSS}"
    assert runner.calls == []
    assert finder.asked == []


def test_a_title_that_is_not_plain_fails_before_anything_runs() -> None:
    runner = _Runner(_ended(0))
    with pytest.raises(WindowFailed) as failed:
        window_words(LINE, "Fairband-A&B", _opener(runner), 8470, 17)
    assert str(failed.value) == f"`Fairband-A&B` {CROSS}"
    assert runner.calls == []


# The window command's run.


def test_the_words_run_as_a_list() -> None:
    runner = _Runner(_ended(0))
    finder = _Finder("wt.exe")
    words = ("wt.exe", "-w", "0", "new-tab", "bash", "-l", LAUNCHER, PYTHON, "8470", "17")
    assert open_window(words, _opener(runner, finder)) is None
    assert finder.asked == ["wt.exe"]
    assert len(runner.calls) == 1
    assert type(runner.calls[0]) is list
    assert runner.calls[0] == list(words)


def test_a_program_the_finder_does_not_find_runs_nothing() -> None:
    runner = _Runner(_ended(0))
    sentence = _failure(["wt.exe", "-w", "0"], _opener(runner, _Finder()))
    assert sentence == "`wt.exe` was not found"
    assert runner.calls == []


def test_a_program_the_run_does_not_find() -> None:
    runner = _Runner(FileNotFoundError(2, "No such file or directory", "wt.exe"))
    assert _failure(["wt.exe", "-w", "0"], _opener(runner)) == "`wt.exe` was not found"


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (
            PermissionError(13, "Permission denied", "wt.exe"),
            "[Errno 13] Permission denied: 'wt.exe'",
        ),
        (OSError("the exec format is wrong"), "the exec format is wrong"),
    ],
)
def test_a_command_that_cannot_start(error: OSError, text: str) -> None:
    sentence = _failure(["wt.exe"], _opener(_Runner(error)))
    assert sentence == f"the window command could not start: {text}"


def test_a_command_that_does_not_end_in_time() -> None:
    runner = _Runner(subprocess.TimeoutExpired(["wt.exe"], WINDOW_LIMIT_S))
    sentence = _failure(["wt.exe"], _opener(runner))
    assert sentence == "the window command did not end in 15 seconds"


def test_the_limit_is_15_seconds() -> None:
    assert WINDOW_LIMIT_S == 15


@pytest.mark.parametrize(
    ("error_output", "sentence"),
    [
        (b"0x80070002\n", "the window command ended with exit code 1: 0x80070002"),
        (
            b"\n  \r\n  first line  \nsecond line\n",
            "the window command ended with exit code 1: first line",
        ),
        (
            b"\xff\xfe bad bytes",
            "the window command ended with exit code 1: "
            + "\N{REPLACEMENT CHARACTER}" * 2
            + " bad bytes",
        ),
        (b"", "the window command ended with exit code 1"),
        (b" \n\t\r\n", "the window command ended with exit code 1"),
        (b"\0\0\0", "the window command ended with exit code 1"),
    ],
)
def test_a_command_that_ends_with_another_exit_code(error_output: bytes, sentence: str) -> None:
    assert _failure(["wt.exe"], _opener(_Runner(_ended(1, error_output)))) == sentence


def test_error_output_in_utf_16_reads_as_its_line() -> None:
    error_output = "The system cannot find the file\r\n".encode("utf-16-le")
    assert b"\0" in error_output
    sentence = _failure(["wt.exe"], _opener(_Runner(_ended(1, error_output))))
    assert sentence == "the window command ended with exit code 1: The system cannot find the file"


def test_a_long_line_is_cut_to_200_characters() -> None:
    sentence = _failure(["wt.exe"], _opener(_Runner(_ended(2, b"x" * 500 + b"\nmore\n"))))
    assert sentence == "the window command ended with exit code 2: " + "x" * 200


def test_an_exit_code_of_0_is_no_failure_whatever_the_error_output() -> None:
    assert open_window(["wt.exe"], _opener(_Runner(_ended(0, b"a warning\n")))) is None


# The system opener: its runner runs this Python only, which opens no window.


def test_the_system_opener() -> None:
    opener = system_opener()
    assert opener.which is shutil.which
    assert opener.python == sys.executable
    assert opener.environ is os.environ
    packaged = resources.files("fairband.launch").joinpath("launcher.sh")
    assert opener.launcher == str(packaged)
    assert Path(opener.launcher).is_file()


def test_the_system_runner_answers_the_exit_code_and_the_error_output() -> None:
    script = "import sys; sys.stdout.write('out'); sys.stderr.write('fault'); sys.exit(3)"
    result = system_opener().run([sys.executable, "-c", script])
    # The standard output is not kept.
    assert (result.returncode, result.stdout, result.stderr) == (3, None, b"fault")


def test_the_system_runner_answers_at_the_commands_exit_not_its_outputs_end() -> None:
    # The child starts a grandchild that inherits its output and sleeps 5 seconds, writes one line
    # and exits at once, as a window command may leave a program running. The run answers at the
    # child's exit, not when the grandchild lets go of the output; the grandchild ends by itself.
    sleeper = "import time; time.sleep(5)"
    script = (
        "import os, subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {sleeper!r}]); "
        "sys.stderr.write('the window opened\\n'); sys.stderr.flush(); os._exit(0)"
    )
    started = time.monotonic()
    result = system_opener().run([sys.executable, "-c", script])
    assert time.monotonic() - started < 3
    assert (result.returncode, result.stderr) == (0, b"the window opened\n")


def test_the_system_runner_passes_each_word_whole_with_no_shell() -> None:
    script = "import sys; sys.stderr.write(repr(sys.argv[1:]))"
    words = (sys.executable, "-c", script, "$HOME; echo x", "two words", "'q'")
    result = system_opener().run(words)
    assert result.returncode == 0
    assert result.stderr.decode() == repr(["$HOME; echo x", "two words", "'q'"])


def test_the_system_runner_closes_the_input() -> None:
    script = (
        "import os, sys; sys.exit(0 if os.path.samestat(os.fstat(0), os.stat(os.devnull)) else 5)"
    )
    assert system_opener().run([sys.executable, "-c", script]).returncode == 0


def test_the_system_runner_stops_at_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    # The limit, shortened so the test does not wait 15 seconds, is read at each run.
    monkeypatch.setattr("fairband.launch.command.WINDOW_LIMIT_S", 0.2)
    with pytest.raises(subprocess.TimeoutExpired):
        system_opener().run([sys.executable, "-c", "import time; time.sleep(30)"])


# The agent's words, for item 12 of QCOM in mode full report.


def test_the_agent_words_of_spec_6_3_with_every_field_set() -> None:
    assert agent_words(VALUES, QCOM) == [
        "claude",
        "--model",
        "claude-opus-5-5",
        "--effort",
        "xhigh",
        "--permission-mode",
        "auto",
        "/fairband-research work item 12",
    ]


@pytest.mark.parametrize(
    ("name", "option", "value"),
    [
        ("claude.model", "--model", "claude-opus-5-5"),
        ("claude.effort", "--effort", "xhigh"),
        ("claude.permission_mode", "--permission-mode", "auto"),
    ],
)
def test_an_option_alone(name: str, option: str, value: str) -> None:
    values = NONE_SET | {name: value}
    assert agent_words(values, QCOM) == [
        "claude",
        option,
        value,
        "/fairband-research work item 12",
    ]


def test_no_option_set() -> None:
    assert agent_words(NONE_SET, QCOM) == ["claude", "/fairband-research work item 12"]


def test_the_prompt_is_one_word_with_its_three_names_replaced() -> None:
    values = NONE_SET | {"claude.prompt": "/fairband-research {mode} of {symbol}, work item {item}"}
    words = agent_words(values, QCOM)
    assert words == ["claude", "/fairband-research full report of QCOM, work item 12"]


def test_a_name_twice_is_replaced_twice_and_a_lone_brace_stays() -> None:
    values = NONE_SET | {"claude.prompt": "{symbol} work item {item} } item {item}"}
    assert agent_words(values, AAPL)[-1] == "AAPL work item 3 } item 3"


def test_a_command_of_two_words_keeps_both_before_the_options() -> None:
    values = VALUES | {"claude.command": "'/opt/my tools/claude' --verbose"}
    assert agent_words(values, QCOM) == [
        "/opt/my tools/claude",
        "--verbose",
        "--model",
        "claude-opus-5-5",
        "--effort",
        "xhigh",
        "--permission-mode",
        "auto",
        "/fairband-research work item 12",
    ]


def test_the_last_word_of_a_test() -> None:
    assert TEST_PROMPT == "/fairband-research launch test"
    assert agent_words(VALUES, None)[-1] == TEST_PROMPT
    assert agent_words(NONE_SET, None) == ["claude", "/fairband-research launch test"]


# The launcher script.


def _launcher_lines() -> list[str]:
    text = resources.files("fairband.launch").joinpath("launcher.sh").read_text(encoding="utf-8")
    assert text.endswith("\n")
    return text.splitlines()


def test_the_launcher_names_no_shell_and_holds_one_exec() -> None:
    """A login shell runs the file, so no first line names one; ``-P`` keeps the window's folder,
    where a ``json.py`` of the user's could stand, off the import path."""
    lines = _launcher_lines()
    assert lines[0].startswith("# ")
    assert "#!" not in lines[0] and "bash" not in lines[0]
    assert len(lines[0]) <= 100
    assert lines[1:] == ['exec "$1" -P -m fairband launch "$2" "$3"']


def test_the_launcher_starts_its_first_word_with_the_other_two_whole(tmp_path: Path) -> None:
    # A stand-in for the server's Python that writes the words it gets; bash runs the script as the
    # window does, but not as a login shell, so the test reads no profile.
    stand_in = tmp_path / "stand-in"
    stand_in.write_text(
        f"#!{sys.executable}\nimport sys\nprint(repr(sys.argv[1:]))\n", encoding="utf-8"
    )
    stand_in.chmod(0o755)
    launcher = str(resources.files("fairband.launch").joinpath("launcher.sh"))
    result = subprocess.run(
        ["bash", launcher, str(stand_in), "8470", "17"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.decode().strip() == repr(["-P", "-m", "fairband", "launch", "8470", "17"])
