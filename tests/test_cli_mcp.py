"""The ``mcp`` command and the ``fairband`` console script (spec 2026-11-06 Tier 2, 14 and 15.1):
``uv run fairband mcp [--port 8470]`` serves the tools over stdio against the web server on that
port."""

import tomllib
from pathlib import Path

import pytest

import fairband.__main__ as cli
from fairband.__main__ import parse_args

PYPROJECT = Path(__file__).parents[1] / "pyproject.toml"


def test_mcp_takes_the_port() -> None:
    assert parse_args(["mcp", "--port", "9000"]).port == 9000
    assert parse_args(["mcp"]).port == 8470


def test_the_mcp_command_serves_the_tools_on_the_port(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[int] = []
    monkeypatch.setattr(cli, "run_mcp", served.append)
    assert cli.main(["mcp", "--port", "9000"]) == 0
    assert served == [9000]


def test_the_console_script_runs_the_command_line() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    assert project["scripts"] == {"fairband": "fairband.__main__:main"}
    assert any(d.startswith("mcp>=2.3.0") for d in project["dependencies"])
