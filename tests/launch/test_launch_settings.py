"""The launch file (spec 2026-11-16 agent launch, 7.1 and 7.2): its defaults, its rules, the
sentence a file the server cannot use reads as, the save that lays changes over the file as it is
now, and the suggested window command. Every file lives in a temporary config folder."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from fairband.launch.settings import (
    DEFAULTS,
    EFFORTS,
    FILE_NAME,
    MODES,
    NAMES,
    LaunchFile,
    check_value,
    read_launch_file,
    suggested_window_command,
    write_launch_file,
)

# The example of spec 7.2, byte for byte.
EXAMPLE = """{
  "window_command": "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e",
  "claude": {
    "command": "claude",
    "prompt": "/fairband-research work item {item}",
    "model": "claude-opus-5-5",
    "effort": "xhigh",
    "permission_mode": "auto",
    "folder": "~/fairband-research"
  }
}
"""
EXAMPLE_VALUES = {
    "window_command": "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e",
    "claude.command": "claude",
    "claude.prompt": "/fairband-research work item {item}",
    "claude.model": "claude-opus-5-5",
    "claude.effort": "xhigh",
    "claude.permission_mode": "auto",
    "claude.folder": "~/fairband-research",
}
EFFORT_WORDS = "is `extreme`; it is one of low, medium, high, xhigh, max"


def _put(config_dir: Path, text: str | bytes) -> Path:
    path = config_dir / FILE_NAME
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


def _document(values: dict[str, str]) -> dict[str, Any]:
    """The file's JSON object for dotted names: ``claude.model`` is ``claude`` then ``model``."""
    document: dict[str, Any] = {}
    for name, value in values.items():
        top, _, inner = name.partition(".")
        if inner:
            document.setdefault(top, {})[inner] = value
        else:
            document[top] = value
    return document


def _with(name: str, value: str) -> str:
    """The example's text with ``name`` set to ``value``."""
    return json.dumps(_document(EXAMPLE_VALUES | {name: value}), indent=2)


# The defaults and the names.


def test_the_names_and_their_defaults() -> None:
    assert FILE_NAME == "launch.json"
    assert NAMES == (
        "window_command",
        "claude.command",
        "claude.prompt",
        "claude.model",
        "claude.effort",
        "claude.permission_mode",
        "claude.folder",
    )
    assert DEFAULTS == {
        "window_command": "",
        "claude.command": "claude",
        "claude.prompt": "/fairband-research work item {item}",
        "claude.model": "",
        "claude.effort": "",
        "claude.permission_mode": "",
        "claude.folder": "~/fairband-research",
    }
    assert EFFORTS == ("low", "medium", "high", "xhigh", "max")
    assert MODES == ("acceptEdits", "auto", "bypassPermissions", "dontAsk", "manual", "plan")


def test_no_file_is_every_default_and_not_ready(tmp_path: Path) -> None:
    launch = read_launch_file(tmp_path)
    assert launch == LaunchFile(values=DEFAULTS, error=None)
    assert not launch.ready


def test_no_config_folder_is_every_default(tmp_path: Path) -> None:
    assert read_launch_file(tmp_path / "missing") == LaunchFile(values=DEFAULTS, error=None)


def test_the_example_reads_back_name_for_name_and_is_ready(tmp_path: Path) -> None:
    _put(tmp_path, EXAMPLE)
    launch = read_launch_file(tmp_path)
    assert launch.error is None
    assert launch.values == EXAMPLE_VALUES
    assert list(launch.values) == list(NAMES)
    assert launch.ready


def test_a_name_left_out_has_its_default(tmp_path: Path) -> None:
    _put(tmp_path, '{"claude": {"model": "opus"}}')
    launch = read_launch_file(tmp_path)
    assert launch == LaunchFile(values=DEFAULTS | {"claude.model": "opus"}, error=None)
    assert list(launch.values) == list(NAMES)


def test_an_empty_object_is_every_default(tmp_path: Path) -> None:
    _put(tmp_path, "{}")
    assert read_launch_file(tmp_path) == LaunchFile(values=DEFAULTS, error=None)


@pytest.mark.parametrize("command", ["", "   ", "\t\n"])
def test_a_window_command_of_no_word_is_not_ready(tmp_path: Path, command: str) -> None:
    _put(tmp_path, json.dumps({"window_command": command}))
    launch = read_launch_file(tmp_path)
    assert launch.error is None
    assert not launch.ready


def test_a_window_command_alone_is_ready(tmp_path: Path) -> None:
    _put(tmp_path, json.dumps({"window_command": "xterm -e"}))
    assert read_launch_file(tmp_path).ready


# The rules of spec 7.1.

BROKEN = [
    ("window_command", 'wt.exe "new-tab', "does not split into words: No closing quotation"),
    ("window_command", "wt.exe new-tab \\", "does not split into words: No escaped character"),
    ("claude.command", "", "holds no word"),
    ("claude.command", "   ", "holds no word"),
    ("claude.command", "-p claude", "starts with -"),
    ("claude.command", "claude 'x", "does not split into words: No closing quotation"),
    ("claude.prompt", "/fairband-research work item {item}\nnow", "is not one line"),
    ("claude.prompt", "/fairband-research work item {item}\r", "is not one line"),
    ("claude.prompt", "{item}" + "x" * 495, "is longer than 500 characters"),
    ("claude.prompt", "/fairband-research work item", "does not hold {item}"),
    (
        "claude.prompt",
        "/fairband-research {item} for {ticker}",
        "holds {ticker}; a name in braces is item, symbol or mode",
    ),
    ("claude.prompt", "{item} {}", "holds {}; a name in braces is item, symbol or mode"),
    ("claude.prompt", "{item }", "does not hold {item}"),
    ("claude.prompt", "{item} {Item}", "holds {Item}; a name in braces is item, symbol or mode"),
    ("claude.model", "claude opus", "holds white space"),
    ("claude.model", "opus\t", "holds white space"),
    ("claude.model", "--dangerously-skip-permissions", "starts with -"),
    ("claude.model", "m" * 101, "is longer than 100 characters"),
    ("claude.effort", "extreme", EFFORT_WORDS),
    ("claude.effort", "XHIGH", "is `XHIGH`; it is one of low, medium, high, xhigh, max"),
    (
        "claude.permission_mode",
        "bypass",
        "is `bypass`; it is one of acceptEdits, auto, bypassPermissions, dontAsk, manual, plan",
    ),
    ("claude.folder", "fairband-research", "is not an absolute path"),
    ("claude.folder", "", "is not an absolute path"),
    ("claude.folder", "./research", "is not an absolute path"),
    ("claude.folder", "~nosuchuser-of-fairband/research", "is not an absolute path"),
    # A NUL byte breaks one rule of every name, checked before the name's own.
    ("window_command", "wt.exe\x00 -e", "holds a NUL byte"),
    ("claude.command", "-\x00", "holds a NUL byte"),
    ("claude.prompt", "/fairband-research work item\x00", "holds a NUL byte"),
    ("claude.model", "opus\x00", "holds a NUL byte"),
    ("claude.effort", "high\x00", "holds a NUL byte"),
    ("claude.permission_mode", "auto\x00", "holds a NUL byte"),
    ("claude.folder", "~\x00x", "holds a NUL byte"),
]


@pytest.mark.parametrize(("name", "value", "words"), BROKEN)
def test_check_value_names_the_rule_broken(name: str, value: str, words: str) -> None:
    assert check_value(name, value) == words


@pytest.mark.parametrize(("name", "value", "words"), BROKEN)
def test_a_file_that_breaks_a_rule_reads_as_its_sentence(
    tmp_path: Path, name: str, value: str, words: str
) -> None:
    _put(tmp_path, _with(name, value))
    launch = read_launch_file(tmp_path)
    assert launch.error == f"launch.json: `{name}` {words}"
    assert launch.values == DEFAULTS
    assert not launch.ready


KEPT = [
    ("window_command", ""),
    ("window_command", "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e"),
    ("window_command", "xterm -title '{title}' -e"),
    ("claude.command", "claude"),
    ("claude.command", "npx -y @anthropic-ai/claude-code"),
    ("claude.command", "/home/me/.local/bin/claude --verbose"),
    ("claude.prompt", "/fairband-research work item {item}"),
    ("claude.prompt", "/fairband-research {mode} of {symbol}, work item {item}"),
    ("claude.prompt", "{item}" + "x" * 494),
    ("claude.model", ""),
    ("claude.model", "opus"),
    ("claude.model", "claude-opus-5-5"),
    ("claude.model", "m" * 100),
    ("claude.folder", "~/fairband-research"),
    ("claude.folder", "~"),
    ("claude.folder", "/srv/research"),
]


@pytest.mark.parametrize(("name", "value"), KEPT)
def test_check_value_keeps_a_value_that_breaks_no_rule(name: str, value: str) -> None:
    assert check_value(name, value) is None


@pytest.mark.parametrize("effort", ["", *EFFORTS])
def test_every_effort_and_none_is_kept(effort: str) -> None:
    assert check_value("claude.effort", effort) is None


@pytest.mark.parametrize("mode", ["", *MODES])
def test_every_mode_and_none_is_kept(mode: str) -> None:
    assert check_value("claude.permission_mode", mode) is None


def test_every_default_breaks_no_rule() -> None:
    assert {name: check_value(name, value) for name, value in DEFAULTS.items()} == dict.fromkeys(
        NAMES
    )


# A file the server cannot use (Review Focus 1: a file caught half written).


@pytest.mark.parametrize(
    ("text", "sentence"),
    [
        (EXAMPLE[: len(EXAMPLE) // 2], "launch.json is not valid JSON (line 5)"),
        ("", "launch.json is not valid JSON (line 1)"),
        (
            '{\n  "claude": {\n    "effort": "high",\n    "model": opus\n  }\n}\n',
            "launch.json is not valid JSON (line 4)",
        ),
        ("[]", "launch.json: the file holds no object"),
        ('"wt.exe"', "launch.json: the file holds no object"),
        ("null", "launch.json: the file holds no object"),
        ('{"editor": "vim"}', "launch.json: `editor` is not a name of this file"),
        ('{"claude": {"modle": "opus"}}', "launch.json: `claude.modle` is not a name of this file"),
        ('{"claude": "opus"}', "launch.json: `claude` is not an object"),
        ('{"claude": null}', "launch.json: `claude` is not an object"),
        ('{"claude": {"effort": 5}}', "launch.json: `claude.effort` is not text"),
        ('{"window_command": null}', "launch.json: `window_command` is not text"),
        ('{"claude": {"folder": ["~"]}}', "launch.json: `claude.folder` is not text"),
        # a lone surrogate, which no answer of the server can send as UTF-8
        ('{"claude": {"model": "\\ud800"}}', "launch.json: `claude.model` is not text"),
        ('{"window_command": "wt.exe \\udfff"}', "launch.json: `window_command` is not text"),
    ],
)
def test_a_file_that_cannot_be_used_reads_as_its_sentence(
    tmp_path: Path, text: str, sentence: str
) -> None:
    _put(tmp_path, text)
    launch = read_launch_file(tmp_path)
    assert launch == LaunchFile(values=DEFAULTS, error=sentence)
    assert not launch.ready


def test_the_whole_file_read_after_a_half_one_is_right(tmp_path: Path) -> None:
    _put(tmp_path, EXAMPLE[: len(EXAMPLE) // 2])
    assert read_launch_file(tmp_path).error is not None
    _put(tmp_path, EXAMPLE)
    assert read_launch_file(tmp_path) == LaunchFile(values=EXAMPLE_VALUES, error=None)


def test_a_file_that_is_not_utf8_is_not_valid_json(tmp_path: Path) -> None:
    _put(tmp_path, b'{\n  "claude": {\n    "folder": "~/r\xe9search"\n  }\n}\n')
    assert read_launch_file(tmp_path) == LaunchFile(
        values=DEFAULTS, error="launch.json is not valid JSON (line 3)"
    )


def test_a_number_of_more_digits_than_python_converts_is_not_text(tmp_path: Path) -> None:
    _put(tmp_path, '{"claude": {"effort": ' + "1" * 5000 + "}}")
    assert read_launch_file(tmp_path) == LaunchFile(
        values=DEFAULTS, error="launch.json: `claude.effort` is not text"
    )


def test_nesting_too_deep_to_decode_is_not_valid_json(tmp_path: Path) -> None:
    _put(tmp_path, "[" * 100_000)
    assert read_launch_file(tmp_path) == LaunchFile(
        values=DEFAULTS, error="launch.json is not valid JSON (line 1)"
    )


def test_a_folder_in_the_files_place_cannot_be_read(tmp_path: Path) -> None:
    path = tmp_path / FILE_NAME
    path.mkdir()
    with pytest.raises(OSError) as caught:
        path.read_bytes()
    assert read_launch_file(tmp_path) == LaunchFile(
        values=DEFAULTS, error=f"launch.json cannot be read: {caught.value}"
    )


@pytest.mark.skipif(os.geteuid() == 0, reason="the superuser reads a file of any permission")
def test_a_file_without_permission_cannot_be_read(tmp_path: Path) -> None:
    path = _put(tmp_path, EXAMPLE)
    path.chmod(0)
    try:
        with pytest.raises(PermissionError) as caught:
            path.read_bytes()
        launch = read_launch_file(tmp_path)
    finally:
        path.chmod(0o600)
    assert launch == LaunchFile(
        values=DEFAULTS, error=f"launch.json cannot be read: {caught.value}"
    )


@pytest.mark.parametrize(
    ("document", "sentence"),
    [
        # A name the file does not know comes before a value that is not text.
        ({"claude": {"effort": 5}, "editor": "vim"}, "`editor` is not a name of this file"),
        # The top level's names come before those under `claude`.
        ({"claude": {"modle": "opus"}, "editor": "vim"}, "`editor` is not a name of this file"),
        ({"claude": "opus", "editor": "vim"}, "`editor` is not a name of this file"),
        # A value that is not text comes before a broken rule.
        ({"window_command": '"', "claude": {"folder": 5}}, "`claude.folder` is not text"),
        # Broken rules come by the order of NAMES.
        (
            {"claude": {"folder": "research", "effort": "extreme"}},
            f"`claude.effort` {EFFORT_WORDS}",
        ),
    ],
)
def test_the_first_fault_found_is_the_sentence(
    tmp_path: Path, document: dict[str, Any], sentence: str
) -> None:
    _put(tmp_path, json.dumps(document))
    assert read_launch_file(tmp_path).error == f"launch.json: {sentence}"


# The save.


def test_a_save_writes_every_name_in_order_with_the_examples_layout(tmp_path: Path) -> None:
    launch = write_launch_file(tmp_path, EXAMPLE_VALUES)
    assert launch == LaunchFile(values=EXAMPLE_VALUES, error=None)
    assert (tmp_path / FILE_NAME).read_text(encoding="utf-8") == EXAMPLE
    assert sorted(os.listdir(tmp_path)) == [FILE_NAME]


def test_a_save_writes_the_defaults_too(tmp_path: Path) -> None:
    write_launch_file(tmp_path, {"claude.effort": "high"})
    assert json.loads((tmp_path / FILE_NAME).read_text(encoding="utf-8")) == {
        "window_command": "",
        "claude": {
            "command": "claude",
            "prompt": "/fairband-research work item {item}",
            "model": "",
            "effort": "high",
            "permission_mode": "",
            "folder": "~/fairband-research",
        },
    }


def test_a_save_writes_a_letter_beyond_ascii_as_itself(tmp_path: Path) -> None:
    write_launch_file(tmp_path, {"claude.folder": "/srv/recherche-é"})
    assert '"folder": "/srv/recherche-é"' in (tmp_path / FILE_NAME).read_text(encoding="utf-8")
    assert read_launch_file(tmp_path).values["claude.folder"] == "/srv/recherche-é"


def test_a_save_makes_the_config_folder(tmp_path: Path) -> None:
    config_dir = tmp_path / ".config" / "fairband"
    write_launch_file(config_dir, {"window_command": "xterm -e"})
    assert read_launch_file(config_dir).values == DEFAULTS | {"window_command": "xterm -e"}


def test_a_save_lays_its_change_over_the_file_as_it_is_now(tmp_path: Path) -> None:
    write_launch_file(tmp_path, EXAMPLE_VALUES)
    # Another writer changes the model after the form was loaded.
    _put(tmp_path, _with("claude.model", "opus"))
    launch = write_launch_file(tmp_path, {"claude.effort": "high"})
    expected = EXAMPLE_VALUES | {"claude.model": "opus", "claude.effort": "high"}
    assert launch == LaunchFile(values=expected, error=None)
    assert read_launch_file(tmp_path) == LaunchFile(values=expected, error=None)


def test_a_save_over_an_unusable_file_starts_from_the_defaults(tmp_path: Path) -> None:
    _put(tmp_path, _with("claude.effort", "extreme"))
    launch = write_launch_file(tmp_path, {"claude.model": "opus"})
    expected = DEFAULTS | {"claude.model": "opus"}
    assert launch == LaunchFile(values=expected, error=None)
    assert read_launch_file(tmp_path) == LaunchFile(values=expected, error=None)


def test_a_save_over_a_half_written_file_writes_a_good_one(tmp_path: Path) -> None:
    _put(tmp_path, EXAMPLE[: len(EXAMPLE) // 2])
    write_launch_file(tmp_path, {"window_command": "xterm -e"})
    launch = read_launch_file(tmp_path)
    assert launch.error is None and launch.ready


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"claude.effort": "extreme"}, f"claude.effort: {EFFORT_WORDS}"),
        ({"claude.model": "opus", "claude.folder": "r"}, "claude.folder: is not an absolute path"),
        ({"editor": "vim"}, "editor: is not a name of the Agents section"),
        ({"claude.effort": 5}, "claude.effort: is not text"),
        ({"claude.model": "\ud800"}, "claude.model: is not text"),
        ({"claude.model": "opus\x00"}, "claude.model: holds a NUL byte"),
    ],
)
def test_a_refused_save_writes_nothing(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    # A layout of the founder's own, which a save would rewrite.
    text = json.dumps(_document(EXAMPLE_VALUES))
    path = _put(tmp_path, text)
    before = path.read_bytes()
    with pytest.raises(ValueError) as caught:
        write_launch_file(tmp_path, changes)
    assert str(caught.value) == message
    assert path.read_bytes() == before
    assert sorted(os.listdir(tmp_path)) == [FILE_NAME]


def test_a_refused_save_with_no_file_writes_none(tmp_path: Path) -> None:
    config_dir = tmp_path / "fairband"
    with pytest.raises(ValueError, match="^claude.effort: is `extreme`"):
        write_launch_file(config_dir, {"claude.effort": "extreme"})
    assert not config_dir.exists()


def test_a_save_that_fails_to_replace_leaves_the_file_and_no_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _put(tmp_path, EXAMPLE)

    def refuse(source: str, target: str) -> None:
        raise OSError("the disk refused")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError, match="the disk refused"):
        write_launch_file(tmp_path, {"claude.effort": "high"})
    assert path.read_text(encoding="utf-8") == EXAMPLE
    assert sorted(os.listdir(tmp_path)) == [FILE_NAME]


# The suggested window command.


def _finds(*programs: str) -> Any:
    def which(program: str) -> str | None:
        return f"/mnt/c/Windows/{program}" if program in programs else None

    return which


def test_the_suggested_line_under_wsl_with_windows_terminal() -> None:
    line = suggested_window_command({"WSL_DISTRO_NAME": "Ubuntu"}, _finds("wt.exe"))
    assert line == "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e"


def test_the_suggested_line_keeps_a_distribution_of_plain_word_signs() -> None:
    line = suggested_window_command({"WSL_DISTRO_NAME": "Ubuntu-24.04"}, _finds("wt.exe"))
    assert line == "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu-24.04 -e"


@pytest.mark.parametrize(
    "environ",
    [{}, {"WSL_DISTRO_NAME": ""}, {"WSL_DISTRO_NAME": "My Ubuntu"}, {"WSL_DISTRO_NAME": "a;b"}],
)
def test_no_suggested_line_without_a_plain_distribution_name(environ: dict[str, str]) -> None:
    assert suggested_window_command(environ, _finds("wt.exe")) is None


def test_no_suggested_line_without_windows_terminal() -> None:
    assert suggested_window_command({"WSL_DISTRO_NAME": "Ubuntu"}, _finds()) is None
