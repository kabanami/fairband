"""The ``launch`` command (spec 2026-11-16 agent launch, 6.2): ``fairband launch <port> <launch
id>``, which the launcher script runs in the window the server opened. The launcher is a double
here: it records its call, so nothing starts and nothing calls a server."""

import logging
from collections.abc import Iterator
from typing import Any

import pytest

import fairband.__main__ as cli
from fairband.__main__ import parse_args

QUIET = ("httpx", "httpcore")


@pytest.fixture
def loggers() -> Iterator[None]:
    """The levels of httpx's and httpcore's loggers, put back after the test."""
    levels = {name: logging.getLogger(name).level for name in QUIET}
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.NOTSET)
    yield
    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)


def test_launch_takes_the_port_and_the_launch_id() -> None:
    args = parse_args(["launch", "8470", "17"])
    assert (args.command, args.port, args.launch_id) == ("launch", 8470, 17)


@pytest.mark.parametrize("words", [["launch", "8470", "seventeen"], ["launch", "port", "17"]])
def test_launch_refuses_a_word_that_is_no_number(words: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        parse_args(words)
    assert raised.value.code == 2


def test_the_help_says_the_launchers_script_calls_it() -> None:
    assert "the launcher's script calls it" in " ".join(cli._build_parser().format_help().split())


def test_the_command_runs_the_launcher_with_httpx_quiet(
    monkeypatch: pytest.MonkeyPatch, loggers: None
) -> None:
    calls: list[tuple[Any, ...]] = []

    def launcher(port: int, launch_id: int) -> int:
        levels = tuple(logging.getLogger(name).level for name in QUIET)
        calls.append((port, launch_id, levels))
        return 1

    monkeypatch.setattr(cli, "run_launcher", launcher)
    assert cli.main(["launch", "8470", "17"]) == 1
    assert calls == [(8470, 17, (logging.WARNING, logging.WARNING))]
    assert logging.getLogger("httpx").level == logging.WARNING
