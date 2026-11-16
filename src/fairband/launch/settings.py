"""The launch file (spec 2026-11-16 agent launch, 7.1 and 7.2): the Agents section's values in
``launch.json``, in the config folder beside ``keys.toml``. It is not the ``settings`` table,
whose rows overlay the policy and feed the settings hash; a launch setting is no policy value.

The file is one JSON object: ``window_command``, and an object ``claude`` with ``command``,
``prompt``, ``model``, ``effort``, ``permission_mode`` and ``folder``. ``NAMES`` writes a name
under ``claude`` with a dot, ``claude.model``. A name left out has its default, and no file is
every default, so launching is off.

``read_launch_file`` reads the file at each call, keeps no copy and never raises. A file the server
cannot use answers the defaults and ``error``, one sentence that names the file and the first
fault found in this order: the file cannot be read, is not JSON, holds no object, holds a name it
does not know (the top level's before those under ``claude``), holds a value that is not text, or
holds a value that breaks a rule of ``check_value`` (by the order of ``NAMES``).

``write_launch_file`` lays its changes over the file as it is now, or over the defaults where the
server cannot use the file, checks every name, and writes the whole file: every name in the order
of ``NAMES``, defaults too, two spaces of indent and a newline at the end, through a temporary file
in the same folder that replaces the old one whole. It makes the config folder where it is
missing. A change it refuses writes nothing.

``suggested_window_command`` answers the Windows Terminal line of spec 6.1 for the WSL
distribution the server runs in.
"""

import json
import os
import re
import shlex
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FILE_NAME = "launch.json"
# The efforts and permission modes of Claude Code 2.1.325. ``bypassPermissions`` is not offered:
# it skips every permission check, and a research session reads web pages a stranger wrote.
EFFORTS = ("low", "medium", "high", "xhigh", "max")
MODES = ("acceptEdits", "auto", "dontAsk", "manual", "plan")
# The file's order and the form's.
NAMES = (
    "window_command",
    "claude.command",
    "claude.prompt",
    "claude.model",
    "claude.effort",
    "claude.permission_mode",
    "claude.folder",
)
DEFAULTS: dict[str, str] = {
    "window_command": "",
    "claude.command": "claude",
    "claude.prompt": "/fairband-research work item {item}",
    "claude.model": "",
    "claude.effort": "",
    "claude.permission_mode": "",
    "claude.folder": "~/fairband-research",
}

_PROMPT_LIMIT = 500
_MODEL_LIMIT = 100
_PROMPT_NAMES = ("item", "symbol", "mode")
_BRACED = re.compile(r"\{([^{}]*)\}")
_PLAIN_WORD = re.compile(r"[A-Za-z0-9_./:@+-]+")


@dataclass(frozen=True)
class LaunchFile:
    """The launch file's values, one for each of ``NAMES``, and ``error``: the sentence of a file
    the server cannot use, whose values are then the defaults; ``None`` for a file it can use and
    for no file."""

    values: dict[str, str]
    error: str | None

    @property
    def ready(self) -> bool:
        """Launching is set up: the file can be used and its window command holds a word."""
        return self.error is None and bool(shlex.split(self.values["window_command"]))


def check_value(name: str, value: str) -> str | None:
    """The rule of spec 7.1 that ``value`` breaks at ``name``, as the words that follow
    ``<name>: ``; ``None`` when it breaks none. A name not in ``NAMES`` is a ``KeyError``."""
    return _RULES[name](value)


def read_launch_file(config_dir: Path) -> LaunchFile:
    """The launch file in ``config_dir`` as it is now: its values, every default where there is
    no file, or the defaults and the sentence of the first fault where the server cannot use it.
    It never raises."""
    try:
        values = _read_values(config_dir / FILE_NAME)
    except _Unusable as fault:
        return LaunchFile(values=dict(DEFAULTS), error=str(fault))
    return LaunchFile(values=values, error=None)


def write_launch_file(config_dir: Path, changes: Mapping[str, str]) -> LaunchFile:
    """Lay ``changes`` over the launch file as it is now, or over the defaults where the server
    cannot use it, and write the whole file. A name not in ``NAMES``, a value that is not text and
    a value that breaks a rule are each a ``ValueError`` of ``<name>: <words>``, and nothing is
    written."""
    for name, value in changes.items():
        if name not in NAMES:
            raise ValueError(f"{name}: is not a name of the Agents section")
        if not isinstance(value, str):
            # A ValueError like every other refusal of a save, so its caller takes one kind.
            raise ValueError(f"{name}: is not text")  # noqa: TRY004
    values = read_launch_file(config_dir).values | dict(changes)
    for name in NAMES:
        rule = check_value(name, values[name])
        if rule is not None:
            raise ValueError(f"{name}: {rule}")
    _replace(config_dir, _file_text(values).encode("utf-8"))
    return LaunchFile(values=values, error=None)


def suggested_window_command(
    environ: Mapping[str, str], which: Callable[[str], str | None]
) -> str | None:
    """The Windows Terminal line of spec 6.1 for the WSL distribution the server runs in: where
    ``environ`` names the distribution in one plain word and ``which`` finds ``wt.exe``; else
    ``None``."""
    distribution = environ.get("WSL_DISTRO_NAME", "")
    if _PLAIN_WORD.fullmatch(distribution) is None or which("wt.exe") is None:
        return None
    return f"wt.exe -w 0 new-tab --title {{title}} wsl.exe -d {distribution} -e"


class _Unusable(Exception):
    """The server cannot use the launch file: the sentence says why and names the file."""


def _read_values(path: Path) -> dict[str, str]:
    """The file's value for each of ``NAMES``, the default where it holds none; every default
    where there is no file. A file the server cannot use is ``_Unusable``."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return dict(DEFAULTS)
    except OSError as error:
        raise _Unusable(f"{FILE_NAME} cannot be read: {error}") from None
    try:
        # A number reads as a float, which has no limit of digits, as an int has: the file holds
        # no number, and any number is a value that is not text.
        document = json.loads(data.decode("utf-8"), parse_int=float)
    except UnicodeDecodeError as error:
        line = data[: error.start].count(b"\n") + 1
        raise _Unusable(f"{FILE_NAME} is not valid JSON (line {line})") from None
    except json.JSONDecodeError as error:
        raise _Unusable(f"{FILE_NAME} is not valid JSON (line {error.lineno})") from None
    except RecursionError:  # nesting deeper than the decoder goes; the line is not known
        raise _Unusable(f"{FILE_NAME} is not valid JSON (line 1)") from None
    if not isinstance(document, dict):
        raise _Unusable(f"{FILE_NAME}: the file holds no object")
    found = _named(document)
    for name in NAMES:
        if name in found and not isinstance(found[name], str):
            raise _Unusable(f"{FILE_NAME}: `{name}` is not text")
    values = {name: found.get(name, DEFAULTS[name]) for name in NAMES}
    for name in NAMES:
        rule = check_value(name, values[name])
        if rule is not None:
            raise _Unusable(f"{FILE_NAME}: `{name}` {rule}")
    return values


def _named(document: dict[str, Any]) -> dict[str, Any]:
    """The file's values by dotted name. A name the file does not know, or a ``claude`` that is not
    an object, is ``_Unusable``: the top level's names are looked at before those under
    ``claude``."""
    for key in document:
        if key not in ("window_command", "claude"):
            raise _Unusable(f"{FILE_NAME}: `{key}` is not a name of this file")
    claude = document.get("claude", {})
    if not isinstance(claude, dict):
        raise _Unusable(f"{FILE_NAME}: `claude` is not an object")
    found = {f"claude.{key}": value for key, value in claude.items()}
    for name in found:
        if name not in NAMES:
            raise _Unusable(f"{FILE_NAME}: `{name}` is not a name of this file")
    if "window_command" in document:
        found["window_command"] = document["window_command"]
    return found


def _file_text(values: Mapping[str, str]) -> str:
    """The whole file: every name in the order of ``NAMES``, a dotted name under its object, two
    spaces of indent and a newline at the end."""
    document: dict[str, Any] = {}
    for name in NAMES:
        top, _, inner = name.partition(".")
        if inner:
            document.setdefault(top, {})[inner] = values[name]
        else:
            document[top] = values[name]
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _replace(config_dir: Path, body: bytes) -> None:
    """Write ``body`` to a temporary file in ``config_dir`` and put it in the launch file's place
    whole; on any failure the temporary file is removed."""
    config_dir.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=config_dir, prefix=f".{FILE_NAME}.", suffix=".part")
    try:
        with os.fdopen(handle, "wb") as temporary:
            temporary.write(body)
        os.replace(name, config_dir / FILE_NAME)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _does_not_split(value: str) -> str | None:
    """The words of a value that does not split into words by the shell's rules; else ``None``."""
    try:
        shlex.split(value)
    except ValueError as error:
        return f"does not split into words: {error}"
    return None


def _window_command(value: str) -> str | None:
    return _does_not_split(value)


def _claude_command(value: str) -> str | None:
    fault = _does_not_split(value)
    if fault is not None:
        return fault
    words = shlex.split(value)
    if not words:
        return "holds no word"
    if words[0].startswith("-"):
        return "starts with -"
    return None


def _prompt(value: str) -> str | None:
    if "\n" in value or "\r" in value:
        return "is not one line"
    if len(value) > _PROMPT_LIMIT:
        return f"is longer than {_PROMPT_LIMIT} characters"
    if "{item}" not in value:
        return "does not hold {item}"
    for name in _BRACED.findall(value):
        if name not in _PROMPT_NAMES:
            return f"holds {{{name}}}; a name in braces is item, symbol or mode"
    return None


def _model(value: str) -> str | None:
    if any(character.isspace() for character in value):
        return "holds white space"
    if value.startswith("-"):
        return "starts with -"
    if len(value) > _MODEL_LIMIT:
        return f"is longer than {_MODEL_LIMIT} characters"
    return None


def _one_of(choices: tuple[str, ...]) -> Callable[[str], str | None]:
    """The rule of a value that is empty or one of ``choices``."""

    def rule(value: str) -> str | None:
        if value == "" or value in choices:
            return None
        return f"is `{value}`; it is one of {', '.join(choices)}"

    return rule


def _folder(value: str) -> str | None:
    try:
        absolute = Path(value).expanduser().is_absolute()
    # ``~user`` of a user whose home cannot be found, or a user name that holds a NUL byte
    except (RuntimeError, ValueError):
        absolute = False
    return None if absolute else "is not an absolute path"


_RULES: dict[str, Callable[[str], str | None]] = {
    "window_command": _window_command,
    "claude.command": _claude_command,
    "claude.prompt": _prompt,
    "claude.model": _model,
    "claude.effort": _one_of(EFFORTS),
    "claude.permission_mode": _one_of(MODES),
    "claude.folder": _folder,
}
