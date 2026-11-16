"""The Agents section's settings routes (spec 2026-11-16 agent launch, 7.1 to 7.3 and 9): the
form of ``launch.json`` in the config folder (``fairband.launch.settings``), and its save. The
file is not the ``settings`` table: the settings routes read and write no database and move no
settings hash. And the launch routes (spec 6, 8, 9 and 12): a launch stored and its window
opened, its read, and the two routes the launcher in the window calls.

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

The three owner routes, ``PUT /api/launch-settings``, ``POST /api/launches`` and the launcher's
``POST /api/launches/{id}/status``, each refuse the agent's principal header with a 403, as their
lists below say. Two 400s come before that 403, from FastAPI's reading of the request: an agent's
request with no ``X-Fairband-Actor`` header, "identify first: the model identifier you run as" (and
a principal header that names neither the owner nor an agent), from the routes' dependency
``identity.writer_of``; and a body of the wrong shape, as every request the routes' types refuse is
(``app``).

``PUT /api/launch-settings`` with ``{"changes": {<name>: <value>}}`` lays the changes over the file
as it is now, not as the form read it, writes the whole file and answers the form again. It
applies every change or none, and like every write needs the ``X-Fairband-Request`` header
(``app``, D11). Its refusals after the two 400s above, the first that applies in this order, each
with nothing written:

- a request with the agent's principal header: 403, "the Agents section is the owner's", before
  the file is read;
- where the request changes the window command, the app has an opener and the new command holds
  a word: a first word the opener's finder does not find, 400, "window_command: `<word>` was not
  found on the server's path". A window command that is empty or only blanks holds no word and is
  not checked; one that is not text, does not split into words or holds a NUL byte is refused by
  the file's rule. A save that leaves the window command as it is does not check the file's: a
  launch checks it again;
- a name not in the Agents section: 400, "<name>: is not a name of the Agents section";
- a value that is not text, not a string or one the server cannot send as UTF-8: 400, "<name>: is
  not text";
- a value that breaks a rule of spec 7.1, a NUL byte first: 400, "<name>: <rule>", the launch
  file's sentence.

A launch as the API sends it (``launch_json``): ``id``; ``itemId``, ``None`` for a test; ``test``;
``agent``; ``state``; ``stage`` and ``detail``, a failure's; ``exitCode``, an end's; ``createdAt``
and ``updatedAt``; ``ageSeconds``, the whole seconds since it was made on the app's clock, never
below 0; ``overdue`` (``store.launches.overdue``); and its item's ``itemState`` and
``claimedBy``, ``None`` for a test.

``POST /api/launches`` with ``{"itemId": <id>}`` or ``{"test": true}`` is the one route that
starts a program. It reads the launch file, stores the launch ``opening`` for the agent
``claude``, and runs the window command (``launch.command``) through the app's opener with the
stored item's symbol in its title and the app's port and the launch's id among its added words: a
list of words, no shell, and no word from the request. The item's check, the in-flight check and
the insert are one ``BEGIN IMMEDIATE`` transaction, which commits before the window command runs,
so a launcher that reports at once finds its launch. The command's result is a second write:
``opened``, or ``failed`` at the ``window`` stage with the sentence of ``WindowFailed``. Any other
error raised while the words are built or run is a failure at the same stage, "the window command
could not start: <the error's text>" (the error's kind where it has no text), logged once with its
traceback under the launch's id, so no launch is left ``opening`` to hold its item; an error of the
second write itself is not caught, and the app's next start marks the launch. A launch the
launcher has already moved on is answered as it is. It answers 201 with the launch. Its refusals
after the two 400s above (a body whose ``itemId`` is not a whole number or whose ``test`` is not
true or false is one of the wrong shape), the first that applies in this order, each with nothing
stored and nothing run:

- a request with the agent's principal header: 403, "a launch is the owner's";
- an app given no opener or no port: 503, "this server opens no window";
- a launch file the server cannot use: 400, its sentence;
- a window command that holds no word: 400, "launching is not set up: see Settings, Agents";
- a body that names neither an item nor a test, or both: 400, "a launch names an item or a test";
- no such item: 404, "no work item <id>";
- an item claimed: 409, "item <id> is claimed by <actor>"; done, declined or dropped: 409,
  "item <id> is <state>";
- a launch in flight for the item: 409, "a window for this request opened <n> seconds ago".

``GET /api/launches/{id}`` answers the launch, and 404, "no launch <id>", for no such launch.

The launcher's two routes follow. ``GET /api/launches/{id}/command`` answers ``{"argv",
"folder"}``: the agent's words (``launch.command.agent_words``) and the folder with ``~`` made the
home, from the launch file as it is now. Its refusals, in this order: 404, "no launch <id>"; 409,
"launch <id> is <state>", past ``opened``; 409 with the item's sentence above once its item is no
longer pending; 400 with the file's sentence once the file cannot be used.

``POST /api/launches/{id}/status`` with ``{"state", "detail", "exitCode"}`` moves the launch and
answers it: ``started``; ``ended``, keeping ``exitCode``; ``failed`` at the ``agent`` stage,
keeping ``detail``. A report's ``detail`` is kept for ``failed`` alone and its ``exitCode`` for
``ended`` alone. Its refusals after the two 400s above, in this order: 403, "a launch is the
owner's", for the agent's principal; 400, "a launcher reports started, ended or failed", for
another state; 400, "a failed report gives its reason", for a failure with no detail or a blank
one; 400, "an ended report gives its exit code", for an end with no ``exitCode``; 404, "no launch
<id>"; 409 with the record's sentence, "a launch that is <from> does not become <to>", for a move
the record refuses.

The two reads are GETs and need no ``X-Fairband-Request`` header; the two posts need it, as every
write does.
"""

import logging
import shlex
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt
from pydantic.alias_generators import to_camel

from fairband.launch.command import (
    Opener,
    WindowFailed,
    agent_words,
    open_window,
    title_of,
    window_words,
)
from fairband.launch.settings import (
    DEFAULTS,
    EFFORTS,
    MODES,
    NAMES,
    LaunchFile,
    check_value,
    is_text,
    read_launch_file,
    suggested_window_command,
    write_launch_file,
)
from fairband.store.db import transaction
from fairband.store.inbox import WorkItem, work_item
from fairband.store.launches import (
    InFlight,
    LaunchRow,
    WrongMove,
    insert_launch,
    launch,
    move_launch,
    opened,
    overdue,
)
from fairband.store.ledger import Writer
from fairband.web.identity import writer_of

logger = logging.getLogger("fairband.web")

OWNERS = "the Agents section is the owner's"
LAUNCH_OWNERS = "a launch is the owner's"
NO_WINDOW = "this server opens no window"
NOT_SET_UP = "launching is not set up: see Settings, Agents"
NAMES_NOTHING = "a launch names an item or a test"
REPORTS = "a launcher reports started, ended or failed"
NO_REASON = "a failed report gives its reason"
NO_EXIT_CODE = "an ended report gives its exit code"
AGENT = "claude"  # the agent a launch starts
_TAKEN = ("opening", "opened")  # the states in which the command read is taken
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
    "claude.permission_mode": (
        "Permission mode",
        _DEFAULT_HELP + " bypassPermissions skips every permission check.",
    ),
    "claude.folder": ("Folder", "Where the session starts. Fairband makes it."),
}
_CHOICES = {"claude.effort": EFFORTS, "claude.permission_mode": MODES}

WriterOf = Annotated[Writer, Depends(writer_of)]


class LaunchSettingsPut(BaseModel):
    changes: dict[str, Any]


class _Body(BaseModel):
    """A request body, its keys camelCase."""

    model_config = ConfigDict(alias_generator=to_camel)


class LaunchPost(_Body):
    """An item's id, or ``test``; a number and a boolean, not text that reads as one."""

    item_id: StrictInt | None = None
    test: StrictBool = False


class LaunchStatus(_Body):
    state: str
    detail: str | None = None
    exit_code: StrictInt | None = None


def launch_json(row: LaunchRow, item: WorkItem | None, now: datetime) -> dict[str, Any]:
    """The launch ``row`` as the API sends it (the module docstring), read at ``now``, with its
    ``item``, ``None`` for a test."""
    item_state = None if item is None else item.state
    return {
        "id": row.id,
        "itemId": row.item_id,
        "test": row.item_id is None,
        "agent": row.agent,
        "state": row.state,
        "stage": row.stage,
        "detail": row.detail,
        "exitCode": row.exit_code,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
        "ageSeconds": max(0, int((now - row.created_at).total_seconds())),
        "overdue": overdue(row, item_state, now),
        "itemState": item_state,
        "claimedBy": None if item is None else item.claimed_by,
    }


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
    it; ``None`` where the changes hold no window command as text (``is_text``), the app has no
    opener, the command breaks a rule of the file (it does not split into words, or holds a NUL
    byte), which the file's rule then refuses, or holds no word, or the program is found."""
    command = changes.get("window_command")
    if opener is None or not is_text(command) or check_value("window_command", command) is not None:
        return None
    words = shlex.split(command)
    if not words or opener.which(words[0]) is not None:
        return None
    return words[0]


def add_launch_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    config_dir: Path,
    opener: Opener | None,
    port: int | None,
    clock: Callable[[], datetime],
) -> None:
    """Register the launch, its read and the launcher's two routes (the module docstring). The
    window command runs through ``opener`` with ``port``, the port the server listens on; without
    either the launch answers 503 and runs nothing. ``clock`` gives the time a launch is made and
    moved and the time it is read at."""

    @app.post("/api/launches", status_code=201)
    def post_launch(body: LaunchPost, writer: WriterOf) -> dict[str, Any]:
        """Store the launch, then open its window (the module docstring)."""
        if writer.principal == "agent":
            raise HTTPException(403, LAUNCH_OWNERS)
        if opener is None or port is None:
            raise HTTPException(503, NO_WINDOW)
        found = read_launch_file(config_dir)
        if found.error is not None:
            raise HTTPException(400, found.error)
        # Never past here without a window command: its six added words alone would run the
        # launcher inside the server.
        if not found.ready:
            raise HTTPException(400, NOT_SET_UP)
        if (body.item_id is not None) == body.test:
            raise HTTPException(400, NAMES_NOTHING)
        with closing(conn_factory()) as conn:
            with transaction(conn, immediate=True):
                item = None if body.item_id is None else _pending(conn, body.item_id)
                try:
                    made = insert_launch(conn, body.item_id, AGENT, clock())
                except InFlight as exc:
                    raise HTTPException(409, str(exc)) from None
            # Committed: the window's launcher may report before the command returns.
            row = _open(conn, made, item, found.values["window_command"], opener, port, clock)
            return launch_json(row, _item_of(conn, row), clock())

    @app.get("/api/launches/{launch_id}")
    def get_launch(launch_id: int) -> dict[str, Any]:
        with closing(conn_factory()) as conn:
            row = _launch_or_404(conn, launch_id)
            item = _item_of(conn, row)
        return launch_json(row, item, clock())

    @app.get("/api/launches/{launch_id}/command")
    def get_launch_command(launch_id: int) -> dict[str, Any]:
        """The agent's words and its folder, for the launcher in the launch's window."""
        with closing(conn_factory()) as conn:
            row = _launch_or_404(conn, launch_id)
            item = _item_of(conn, row)
        if row.state not in _TAKEN:
            raise HTTPException(409, f"launch {launch_id} is {row.state}")
        refusal = None if item is None else _not_pending(item)
        if refusal is not None:
            raise HTTPException(409, refusal)
        found = read_launch_file(config_dir)
        if found.error is not None:
            raise HTTPException(400, found.error)
        folder = Path(found.values["claude.folder"]).expanduser()
        return {"argv": agent_words(found.values, item), "folder": str(folder)}

    @app.post("/api/launches/{launch_id}/status")
    def post_launch_status(launch_id: int, body: LaunchStatus, writer: WriterOf) -> dict[str, Any]:
        """The launcher's report: the launch after the move."""
        if writer.principal == "agent":
            raise HTTPException(403, LAUNCH_OWNERS)
        if body.state not in ("started", "ended", "failed"):
            raise HTTPException(400, REPORTS)
        if body.state == "failed" and not (body.detail or "").strip():
            raise HTTPException(400, NO_REASON)
        if body.state == "ended" and body.exit_code is None:
            raise HTTPException(400, NO_EXIT_CODE)
        at = clock()
        with closing(conn_factory()) as conn:
            try:
                if body.state == "started":
                    row = move_launch(conn, launch_id, "started", at)
                elif body.state == "ended":
                    row = move_launch(conn, launch_id, "ended", at, exit_code=body.exit_code)
                else:
                    row = move_launch(
                        conn, launch_id, "failed", at, stage="agent", detail=body.detail
                    )
            except KeyError:
                raise HTTPException(404, f"no launch {launch_id}") from None
            except WrongMove as exc:
                raise HTTPException(409, str(exc)) from None
            item = _item_of(conn, row)
        return launch_json(row, item, clock())


def _open(
    conn: sqlite3.Connection,
    made: LaunchRow,
    item: WorkItem | None,
    window_command: str,
    opener: Opener,
    port: int,
    clock: Callable[[], datetime],
) -> LaunchRow:
    """Run the window command for the launch ``made`` of ``item`` (``None`` for a test), with no
    transaction open, and write its result: ``opened``, or ``failed`` at the window stage with
    ``WindowFailed``'s sentence, or, for any other error the words' building or run raises, with
    "the window command could not start: <its text>", the error logged; the launch as it then is.
    A launch the launcher has already moved on stays as it is, the record refusing the failure,
    and is answered as it is. An error of the write itself goes to the caller."""
    try:
        words = window_words(window_command, title_of(item), opener, port, made.id)
        open_window(words, opener)
    except WindowFailed as exc:
        sentence = str(exc)
    except Exception as exc:  # any: a launch left opening would hold its item
        logger.warning("launch %d: the window step raised an error", made.id, exc_info=True)
        sentence = f"the window command could not start: {str(exc) or type(exc).__name__}"
    else:
        return opened(conn, made.id, clock())
    try:
        return move_launch(conn, made.id, "failed", clock(), stage="window", detail=sentence)
    except WrongMove:
        return launch(conn, made.id)


def _pending(conn: sqlite3.Connection, item_id: int) -> WorkItem:
    """The item, where it is pending; else 404 for no item or 409 with ``_not_pending``'s
    sentence."""
    try:
        item = work_item(conn, item_id)
    except KeyError:
        raise HTTPException(404, f"no work item {item_id}") from None
    refusal = _not_pending(item)
    if refusal is not None:
        raise HTTPException(409, refusal)
    return item


def _not_pending(item: WorkItem) -> str | None:
    """The sentence of an item no longer pending, by which a launch and its command read are
    refused; ``None`` for a pending one."""
    if item.state == "pending":
        return None
    if item.state == "claimed":
        return f"item {item.id} is claimed by {item.claimed_by}"
    return f"item {item.id} is {item.state}"


def _launch_or_404(conn: sqlite3.Connection, launch_id: int) -> LaunchRow:
    try:
        return launch(conn, launch_id)
    except KeyError:
        raise HTTPException(404, f"no launch {launch_id}") from None


def _item_of(conn: sqlite3.Connection, row: LaunchRow) -> WorkItem | None:
    """The launch's item as it is now; ``None`` for a test."""
    return None if row.item_id is None else work_item(conn, row.item_id)
