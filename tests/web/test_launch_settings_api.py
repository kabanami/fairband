"""The Agents section's settings routes (spec 2026-11-16 agent launch, 7.1 to 7.3 and 9):
``GET /api/launch-settings`` answers the form from ``launch.json`` in the config folder, and
``PUT /api/launch-settings`` lays the owner's changes over the file as it is now and answers the
form again; the company detail read's ``launchReady`` says whether launching is set up. The opener
is a double: its finder knows the programs a test names and its runner fails the test if it is
called, so nothing here opens a window."""

import json
import subprocess
from collections.abc import Iterator, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.web import HEADER, HOST, _settings

from fairband.launch.command import Opener
from fairband.launch.settings import write_launch_file
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.web.app import create_app
from fairband.web.identity import ACTOR_HEADER, IDENTIFY_FIRST, PRINCIPAL_HEADER

URL = "/api/launch-settings"
AGENT = HEADER | {PRINCIPAL_HEADER: "agent", ACTOR_HEADER: "claude-opus-5-5"}
WT_LINE = "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e"
OWNERS = "the Agents section is the owner's"
FIELDS = [
    {
        "name": "window_command",
        "label": "Window command",
        "value": "",
        "default": "",
        "help": "How to open a terminal window. Fairband adds the launcher's words at the end.",
        "choices": None,
        "suggestions": None,
    },
    {
        "name": "claude.command",
        "label": "Claude Code command",
        "value": "claude",
        "default": "claude",
        "help": "The program that starts Claude Code, found on the path of a login shell.",
        "choices": None,
        "suggestions": None,
    },
    {
        "name": "claude.prompt",
        "label": "First prompt",
        "value": "/fairband-research work item {item}",
        "default": "/fairband-research work item {item}",
        "help": "The session's first message. {item}, {symbol} and {mode} are the request's.",
        "choices": None,
        "suggestions": None,
    },
    {
        "name": "claude.model",
        "label": "Model",
        "value": "",
        "default": "",
        "help": (
            "An alias (fable, opus, sonnet) for the newest model of that family, or a full model "
            "name. Empty for Claude Code's own default."
        ),
        "choices": None,
        "suggestions": ["fable", "opus", "sonnet"],
    },
    {
        "name": "claude.effort",
        "label": "Effort",
        "value": "",
        "default": "",
        "help": "Empty for Claude Code's own default.",
        "choices": ["low", "medium", "high", "xhigh", "max"],
        "suggestions": None,
    },
    {
        "name": "claude.permission_mode",
        "label": "Permission mode",
        "value": "",
        "default": "",
        "help": (
            "Empty for Claude Code's own default. bypassPermissions skips every permission check."
        ),
        "choices": ["acceptEdits", "auto", "bypassPermissions", "dontAsk", "manual", "plan"],
        "suggestions": None,
    },
    {
        "name": "claude.folder",
        "label": "Folder",
        "value": "~/fairband-research",
        "default": "~/fairband-research",
        "help": "Where the session starts. Fairband makes it.",
        "choices": None,
        "suggestions": None,
    },
]
SAVED_EFFORT = """{
  "window_command": "",
  "claude": {
    "command": "claude",
    "prompt": "/fairband-research work item {item}",
    "model": "",
    "effort": "xhigh",
    "permission_mode": "",
    "folder": "~/fairband-research"
  }
}
"""


class Finder:
    """The program finder's double: a path for each program in ``known``, ``None`` for the rest,
    and the programs asked."""

    def __init__(self, *known: str) -> None:
        self.known = set(known)
        self.asked: list[str] = []

    def __call__(self, program: str) -> str | None:
        self.asked.append(program)
        return f"/found/{program}" if program in self.known else None


def _never_run(words: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    raise AssertionError(f"the settings routes ran {list(words)}")


def _opener(finder: Finder, environ: dict[str, str]) -> Opener:
    return Opener(
        run=_never_run,
        which=finder,
        python="/usr/bin/python3",
        launcher="/x/launcher.sh",
        environ=environ,
    )


@pytest.fixture
def finder() -> Finder:
    """The finder of a server that finds ``wt.exe`` and ``konsole`` and no other program."""
    return Finder("wt.exe", "konsole")


@pytest.fixture
def served(tmp_path: Path, db_path: Path, policy: Policy, finder: Finder) -> Iterator[TestClient]:
    """A client of an app with a double opener in the WSL distribution ``Ubuntu``; its config
    folder is ``tmp_path / "config"``, as the shared ``client``'s, which has no opener."""
    opener = _opener(finder, {"WSL_DISTRO_NAME": "Ubuntu"})
    app = create_app(_settings(tmp_path, db_path), policy, lambda: connect(db_path), opener=opener)
    client = TestClient(app, base_url=HOST)
    yield client
    client.close()


@pytest.fixture
def launch_file(tmp_path: Path) -> Path:
    return tmp_path / "config" / "launch.json"


def _form(fields: dict[str, str], **head: Any) -> dict[str, Any]:
    """The form the routes answer: ``fields``' values over the defaults, and ``head`` over a
    head of no file error, launching off and the WSL line suggested."""
    answer = {
        "ready": False,
        "fileError": None,
        "suggested": WT_LINE,
        "fields": [
            field | {"value": fields.get(field["name"], field["value"])} for field in FIELDS
        ],
    }
    return answer | head


def _put(client: TestClient, changes: Any, headers: dict[str, str] = HEADER) -> Any:
    return client.put(URL, json={"changes": changes}, headers=headers)


def _launch_ready(client: TestClient) -> bool:
    ready: bool = client.get("/api/companies/AAPL").json()["launchReady"]
    return ready


def test_the_read_with_no_file_answers_every_default_and_launching_off(
    served: TestClient, launch_file: Path
) -> None:
    """The read is a GET with no ``X-Fairband-Request`` header, and it writes nothing."""
    response = served.get(URL)
    assert response.status_code == 200, response.text
    assert response.json() == _form({})
    assert not launch_file.parent.exists()


def test_a_save_answers_the_form_and_writes_the_whole_file(
    served: TestClient, launch_file: Path
) -> None:
    response = _put(served, {"claude.effort": "xhigh"})
    assert response.status_code == 200, response.text
    assert response.json() == _form({"claude.effort": "xhigh"})
    assert served.get(URL).json() == _form({"claude.effort": "xhigh"})
    assert launch_file.read_text(encoding="utf-8") == SAVED_EFFORT


def test_a_saved_window_command_sets_launching_up(served: TestClient, finder: Finder) -> None:
    command = "konsole --title {title} -e"
    response = _put(served, {"window_command": command, "claude.model": "claude-opus-5-5"})
    assert response.status_code == 200, response.text
    fields = {"window_command": command, "claude.model": "claude-opus-5-5"}
    assert response.json() == _form(fields, ready=True)
    assert "konsole" in finder.asked  # the program check's; the suggestion asks for wt.exe


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"bogus": "x"}, "bogus: is not a name of the Agents section"),
        ({"claude.model": 5}, "claude.model: is not text"),
        ({"window_command": None}, "window_command: is not text"),
        (
            {"claude.effort": "extreme"},
            "claude.effort: is `extreme`; it is one of low, medium, high, xhigh, max",
        ),
        ({"claude.prompt": "research it"}, "claude.prompt: does not hold {item}"),
        ({"claude.folder": "research"}, "claude.folder: is not an absolute path"),
        # every change or none: the good model is not written either
        (
            {"claude.model": "opus", "claude.permission_mode": "bypass"},
            (
                "claude.permission_mode: is `bypass`; it is one of acceptEdits, auto, "
                "bypassPermissions, dontAsk, manual, plan"
            ),
        ),
        (
            {"window_command": "xterm -T {title} -e"},
            "window_command: `xterm` was not found on the server's path",
        ),
        (
            {"window_command": "wt.exe --title 'Fairband"},
            "window_command: does not split into words: No closing quotation",
        ),
        # a NUL byte is refused before the program is looked for
        ({"window_command": "wt.exe\x00 -e"}, "window_command: holds a NUL byte"),
        ({"claude.model": "opus\x00"}, "claude.model: holds a NUL byte"),
    ],
)
def test_a_refused_save_is_a_400_with_its_sentence_and_writes_nothing(
    served: TestClient, launch_file: Path, changes: dict[str, Any], detail: str
) -> None:
    assert _put(served, {"claude.effort": "high"}).status_code == 200
    before = launch_file.read_bytes()
    response = _put(served, changes)
    assert (response.status_code, response.json()) == (400, {"detail": detail})
    assert launch_file.read_bytes() == before
    assert served.get(URL).json() == _form({"claude.effort": "high"})


@pytest.mark.parametrize("body", [{}, {"changes": "claude.effort=high"}, {"changes": ["high"]}])
def test_a_body_without_changes_as_an_object_is_a_400_and_writes_nothing(
    served: TestClient, launch_file: Path, body: dict[str, Any]
) -> None:
    response = served.put(URL, json=body, headers=HEADER)
    assert response.status_code == 400, response.text
    assert not launch_file.exists()


def test_the_program_check_asks_the_first_word_of_a_changed_window_command_alone(
    served: TestClient, client: TestClient, finder: Finder, launch_file: Path
) -> None:
    """A window command that is empty or only blanks holds no word and is not checked; a save
    that leaves the window command as it is does not check the file's, which a hand may have
    written; and an app with no opener checks none."""
    response = _put(served, {"window_command": "  "})
    assert response.status_code == 200, response.text
    assert response.json() == _form({"window_command": "  "})
    assert finder.asked == ["wt.exe"]  # the suggestion's alone
    assert _put(served, {"window_command": "konsole -e"}).status_code == 200
    write_launch_file(launch_file.parent, {"window_command": "gone.exe -x"})
    response = _put(served, {"claude.effort": "max"})
    assert response.status_code == 200, response.text
    assert response.json()["fields"][0]["value"] == "gone.exe -x"
    response = _put(client, {"window_command": "xterm -e"})
    assert response.status_code == 200, response.text
    assert response.json()["fields"][0]["value"] == "xterm -e"


def test_an_agents_save_is_a_403_and_writes_nothing(
    served: TestClient, finder: Finder, launch_file: Path
) -> None:
    response = _put(served, {"window_command": "konsole -e"}, AGENT)
    assert (response.status_code, response.json()) == (403, {"detail": OWNERS})
    assert not launch_file.exists()
    assert finder.asked == []
    no_actor = HEADER | {PRINCIPAL_HEADER: "agent"}
    response = _put(served, {"window_command": "konsole -e"}, no_actor)
    assert (response.status_code, response.json()) == (400, {"detail": IDENTIFY_FIRST})
    assert not launch_file.exists()


def test_a_save_without_the_request_header_is_a_403_and_writes_nothing(
    served: TestClient, launch_file: Path
) -> None:
    response = _put(served, {"claude.effort": "high"}, {})
    assert (response.status_code, response.json()) == (
        403,
        {"detail": "missing X-Fairband-Request header"},
    )
    assert not launch_file.exists()


def test_a_file_that_is_not_json_reads_as_the_defaults_and_a_save_writes_it_again(
    served: TestClient, launch_file: Path
) -> None:
    """Review Focus 1: the read never answers 500 for a bad file, and a save over it starts
    from the defaults."""
    launch_file.parent.mkdir()
    launch_file.write_text('{"window_command": "wt.exe",\n', encoding="utf-8")
    response = served.get(URL)
    assert response.status_code == 200, response.text
    fault = "launch.json is not valid JSON (line 2)"
    assert response.json() == _form({}, fileError=fault)
    response = _put(served, {"claude.effort": "xhigh"})
    assert response.status_code == 200, response.text
    assert response.json() == _form({"claude.effort": "xhigh"})
    assert launch_file.read_text(encoding="utf-8") == SAVED_EFFORT
    assert served.get(URL).json()["fileError"] is None


def test_a_lone_surrogate_in_the_file_reads_as_not_text_and_a_save_of_one_is_a_400(
    served: TestClient, launch_file: Path
) -> None:
    """A value that does not encode as UTF-8 cannot go into a JSON answer: the read names it as
    not text, with a 200, so the section loads and a save can repair the file; a save that sends
    one is refused with the save's sentence, the window command's before its program is looked
    for."""
    launch_file.parent.mkdir()
    launch_file.write_text('{"claude": {"model": "\\ud800"}}', encoding="utf-8")
    response = served.get(URL)
    assert response.status_code == 200, response.text
    assert response.json() == _form({}, fileError="launch.json: `claude.model` is not text")
    before = launch_file.read_bytes()
    for name in ("claude.model", "window_command"):
        body = '{"changes": {"' + name + '": "wt.exe \\ud800"}}'
        response = served.put(
            URL, content=body, headers=HEADER | {"Content-Type": "application/json"}
        )
        assert (response.status_code, response.json()) == (400, {"detail": f"{name}: is not text"})
    assert launch_file.read_bytes() == before


def test_a_save_keeps_a_change_made_to_the_file_after_the_form_was_read(
    served: TestClient, launch_file: Path
) -> None:
    """Review Focus 2: the save lays its changes over the file as it is now, not as the form
    read it."""
    assert served.get(URL).json()["fields"][3] == FIELDS[3]
    write_launch_file(launch_file.parent, {"claude.model": "opus"})
    response = _put(served, {"claude.effort": "xhigh"})
    assert response.status_code == 200, response.text
    assert response.json() == _form({"claude.model": "opus", "claude.effort": "xhigh"})
    saved = json.loads(launch_file.read_text(encoding="utf-8"))
    assert (saved["claude"]["model"], saved["claude"]["effort"]) == ("opus", "xhigh")


@pytest.mark.parametrize(
    ("environ", "known"),
    [
        ({}, ("wt.exe",)),  # not under WSL
        ({"WSL_DISTRO_NAME": "Ubuntu"}, ()),  # no wt.exe on the path
        ({"WSL_DISTRO_NAME": "Ubuntu 24.04"}, ("wt.exe",)),  # a name that is not one plain word
    ],
)
def test_no_line_is_suggested_where_the_opener_gives_none(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    environ: dict[str, str],
    known: tuple[str, ...],
) -> None:
    opener = _opener(Finder(*known), environ)
    app = create_app(_settings(tmp_path, db_path), policy, lambda: connect(db_path), opener=opener)
    with closing(TestClient(app, base_url=HOST)) as client:
        assert client.get(URL).json() == _form({}, suggested=None)


def test_an_app_with_no_opener_suggests_no_line(client: TestClient) -> None:
    assert client.get(URL).json() == _form({}, suggested=None)


def test_the_detail_read_says_whether_launching_is_set_up(
    served: TestClient, launch_file: Path
) -> None:
    assert _launch_ready(served) is False  # no file
    assert _put(served, {"claude.effort": "high"}).status_code == 200
    assert _launch_ready(served) is False  # no window command
    assert _put(served, {"window_command": WT_LINE}).status_code == 200
    assert _launch_ready(served) is True
    unusable = {"window_command": WT_LINE, "claude": {"effort": "extreme"}}
    launch_file.write_text(json.dumps(unusable), encoding="utf-8")
    assert _launch_ready(served) is False  # a file the server cannot use


def test_the_launch_settings_touch_no_policy_setting(
    served: TestClient, client: TestClient, db_path: Path, launch_file: Path
) -> None:
    """The launch file is not the ``settings`` table: no row is written, no change logged, and the
    valuation settings' form, its settings hash with it, reads as before."""
    before = client.get("/api/settings").json()
    assert _put(served, {"window_command": WT_LINE, "claude.effort": "max"}).status_code == 200
    assert _put(served, {"claude.effort": "extreme"}).status_code == 400
    assert _put(served, {"claude.model": "opus"}, AGENT).status_code == 403
    launch_file.write_text("not json", encoding="utf-8")
    assert served.get(URL).status_code == 200
    assert _put(served, {"claude.model": "opus"}).status_code == 200
    after = client.get("/api/settings").json()
    assert after["valuedUnder"]["settingsHash"] == before["valuedUnder"]["settingsHash"]
    assert after == before
    with closing(connect(db_path)) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
        logged = conn.execute("SELECT COUNT(*) FROM settings_changes").fetchone()[0]
    assert (rows, logged) == (0, 0)
