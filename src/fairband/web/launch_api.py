"""The Agents section's settings routes (spec 2026-11-16 agent launch, 7.1 to 7.3 and 9): the
form of ``launch.json`` in the config folder (``fairband.launch.settings``), and its save. The
file is not the ``settings`` table: nothing here reads or writes the database or moves a settings
hash.

``GET /api/launch-settings`` reads the file at each request and answers the form: ``ready``,
whether launching is set up (the file can be used and its window command holds a word);
``fileError``, the sentence of a file the server cannot use, whose fields then read the defaults,
or ``None``; ``suggested``, the Windows Terminal line for the WSL distribution the server runs in
(``launch.settings.suggested_window_command``), ``None`` with no opener, where the opener's
environment names no distribution in one plain word, or where its finder finds no ``wt.exe``; and
``fields``, one for each name in the file's order, with its label, value, default, line of help
and choices (a list for the effort and the permission mode, ``None`` for the rest). The read is a
GET and needs no ``X-Fairband-Request`` header; a bad file is a 200 with ``fileError``, never a
500.

``PUT /api/launch-settings`` with ``{"changes": {<name>: <value>}}`` lays the changes over the file
as it is now, not as the form read it, writes the whole file and answers the form again. It
applies every change or none, and like every write needs the ``X-Fairband-Request`` header
(``app``, D11). Its refusals, the first that applies in this order, each with nothing written:

- a request with the agent's principal header: 403, "the Agents section is the owner's", before
  the file is read;
- where the request changes the window command, the app has an opener and the new command holds
  a word: a first word the opener's finder does not find, 400, "window_command: `<word>` was not
  found on the server's path". A window command that is empty or only blanks holds no word and is
  not checked; one that does not split into words is refused by the file's rule. A save that
  leaves the window command as it is does not check the file's: a launch checks it again;
- a name not in the Agents section: 400, "<name>: is not a name of the Agents section";
- a value that is not text: 400, "<name>: is not text";
- a value that breaks a rule of spec 7.1: 400, "<name>: <rule>", the launch file's sentence.
"""

import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from fairband.launch.command import Opener
from fairband.launch.settings import (
    DEFAULTS,
    EFFORTS,
    MODES,
    NAMES,
    LaunchFile,
    read_launch_file,
    suggested_window_command,
    write_launch_file,
)
from fairband.store.ledger import Writer
from fairband.web.identity import writer_of

OWNERS = "the Agents section is the owner's"
_DEFAULT_HELP = "Empty for Claude Code's own default."
# Each name's label and line of help, in the order of ``NAMES``.
_FIELDS: dict[str, tuple[str, str]] = {
    "window_command": (
        "Window command",
        "How to open a terminal window. Fairband adds the launcher's words at the end.",
    ),
    "claude.command": (
        "Claude Code command",
        "The program that starts Claude Code, found on the path of a login shell.",
    ),
    "claude.prompt": (
        "First prompt",
        "The session's first message. {item}, {symbol} and {mode} are the request's.",
    ),
    "claude.model": ("Model", _DEFAULT_HELP),
    "claude.effort": ("Effort", _DEFAULT_HELP),
    "claude.permission_mode": ("Permission mode", _DEFAULT_HELP),
    "claude.folder": ("Folder", "Where the session starts. Fairband makes it."),
}
_CHOICES = {"claude.effort": EFFORTS, "claude.permission_mode": MODES}

WriterOf = Annotated[Writer, Depends(writer_of)]


class LaunchSettingsPut(BaseModel):
    changes: dict[str, Any]


def form_json(found: LaunchFile, opener: Opener | None) -> dict[str, Any]:
    """The form of the launch file ``found``, with the line ``opener`` suggests."""
    suggested = None if opener is None else suggested_window_command(opener.environ, opener.which)
    return {
        "ready": found.ready,
        "fileError": found.error,
        "suggested": suggested,
        "fields": [
            {
                "name": name,
                "label": _FIELDS[name][0],
                "value": found.values[name],
                "default": DEFAULTS[name],
                "help": _FIELDS[name][1],
                "choices": list(_CHOICES[name]) if name in _CHOICES else None,
            }
            for name in NAMES
        ],
    }


def add_launch_settings_routes(app: FastAPI, config_dir: Path, opener: Opener | None) -> None:
    """Register the Agents section's read and save over the launch file in ``config_dir``;
    ``opener``'s finder checks a changed window command's program and, with its environment,
    suggests the Windows Terminal line."""

    @app.get("/api/launch-settings")
    def get_launch_settings() -> dict[str, Any]:
        return form_json(read_launch_file(config_dir), opener)

    @app.put("/api/launch-settings")
    def put_launch_settings(payload: LaunchSettingsPut, writer: WriterOf) -> dict[str, Any]:
        """Apply the changes over the file as it is now, all or none."""
        if writer.principal == "agent":
            raise HTTPException(403, OWNERS)
        missing = _missing_program(payload.changes, opener)
        if missing is not None:
            sentence = f"window_command: `{missing}` was not found on the server's path"
            raise HTTPException(400, sentence)
        try:
            written = write_launch_file(config_dir, payload.changes)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return form_json(written, opener)


def _missing_program(changes: Mapping[str, Any], opener: Opener | None) -> str | None:
    """The first word of the window command in ``changes`` where ``opener``'s finder does not find
    it; ``None`` where the changes hold no window command as text, the app has no opener, the
    command does not split into words (the file's rule refuses it) or holds none, or the program
    is found."""
    command = changes.get("window_command")
    if opener is None or not isinstance(command, str):
        return None
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    if not words or opener.which(words[0]) is not None:
        return None
    return words[0]
