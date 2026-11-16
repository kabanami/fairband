"""The Agents section of the Settings page (spec 2026-11-16 agent launch, 7.3 and 7.4): the form
of ``GET /api/launch-settings``, its Save, Use the Windows Terminal line and Test, which posts a
launch with no work item and follows it. ``agents.js``'s helpers and app.js's ``following``, which
the request button shares, run in node (``support.page``) and the tests read what they return;
the section's drawing, its handlers, settings.js's wiring and the page's styles and script order
are read from the files, as ``tests/web/test_logo_page.py`` reads the logo's."""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from support.page import NODE, STATIC, node
from support.web import _static_file

from fairband.launch.settings import read_launch_file
from fairband.store.launches import LaunchRow
from fairband.web.launch_api import form_json, launch_json

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

AGENTS = STATIC / "agents.js"
OVERDUE = "The window opened, but nothing in it reported after 90 seconds. Check the window."
STARTED = "Claude Code started. Its window should say that the Fairband research skill is loaded."
FIX_FILE = "Correct the file, or save here to write it again with the values shown."


def _function(script: str, name: str) -> str:
    """The text of the script's ``function <name>(``, to its closing brace."""
    start = script.index(f"  function {name}(")
    return script[start : script.index("\n  }\n", start)]


def _in_order(text: str, *parts: str) -> None:
    """Each part is in ``text``, each after the one before it."""
    at = [text.index(part) for part in parts]
    assert at == sorted(at), [parts[i] for i in range(len(parts) - 1) if at[i] > at[i + 1]]


def _rule(selector: str) -> str:
    """The declarations of the page's rule for ``selector``."""
    pattern = rf"\n  {re.escape(selector)} \{{(.*?)\}}"
    found = re.search(pattern, _static_file("index.html"), re.DOTALL)
    assert found is not None, selector
    return " ".join(found.group(1).split())


def _field(name: str, value: str) -> dict[str, Any]:
    return {
        "name": name,
        "label": name,
        "value": value,
        "default": "",
        "help": "",
        "choices": None,
        "suggestions": None,
    }


def _launch(
    state: str,
    *,
    test: bool = False,
    age: int = 10,
    overdue: bool = False,
    item_state: str = "pending",
    stage: str | None = None,
    detail: str | None = None,
    exit_code: int | None = None,
) -> dict[str, Any]:
    """A launch as ``GET /api/launches/{id}`` answers it: a test's, or item 12's."""
    return {
        "id": 7,
        "itemId": None if test else 12,
        "test": test,
        "agent": "claude",
        "state": state,
        "stage": stage,
        "detail": detail,
        "exitCode": exit_code,
        "createdAt": "2026-11-16T10:00:00+00:00",
        "updatedAt": "2026-11-16T10:00:00+00:00",
        "ageSeconds": age,
        "overdue": overdue,
        "itemState": None if test else item_state,
        "claimedBy": None,
    }


# ------------------------------------------------------------------------------- the helpers


def test_edits_gives_the_changed_names_alone() -> None:
    """Save sends the names whose draft is unlike the form's value, with their values: a draft
    typed back to the saved value is no change, and a name with no draft is none."""
    form = {
        "fields": [
            _field("window_command", ""),
            _field("claude.command", "claude"),
            _field("claude.model", ""),
            _field("claude.effort", "high"),
        ]
    }
    draft = {"window_command": "wt.exe -e", "claude.command": "claude", "claude.effort": ""}
    assert node("agents.edits", [form, draft], AGENTS) == {
        "window_command": "wt.exe -e",
        "claude.effort": "",
    }
    assert node("agents.edits", [form, {}], AGENTS) == {}
    assert node("agents.edits", [None, draft], AGENTS) == {}


@pytest.mark.parametrize(
    ("launch", "text", "failed"),
    [
        (_launch("opening", test=True), "Opening a window…", False),
        (
            _launch("failed", test=True, stage="window", detail="`wt.exe` was not found"),
            "Could not open the window: `wt.exe` was not found.",
            True,
        ),
        (_launch("opened", test=True), "The window opened, Claude Code is starting…", False),
        (_launch("opened", test=True, age=91, overdue=True), OVERDUE, True),
        (
            _launch("failed", test=True, stage="agent", detail="`claude` was not found"),
            "The window opened, but Claude Code did not start: `claude` was not found.",
            True,
        ),
        (_launch("started", test=True), STARTED, False),
        (_launch("ended", test=True, exit_code=0), "Claude Code ended (exit code 0).", False),
        (
            _launch("ended", test=True, exit_code=1),
            "Claude Code ended (exit code 1). Check the window.",
            True,
        ),
        (
            _launch("ended", test=True, exit_code=-2),
            "Claude Code ended (exit code -2). Check the window.",
            True,
        ),
    ],
)
def test_the_test_line_says_where_the_test_is(
    launch: dict[str, Any], text: str, failed: bool
) -> None:
    """Spec 7.4's line for each state of the test's launch; a failure's, the overdue line and an
    end with another exit code than 0 take the error style."""
    assert node("agents.testLine", [launch], AGENTS) == {"text": text, "failed": failed}


@pytest.mark.parametrize(
    ("launch", "followed"),
    [
        (_launch("opening"), True),
        (_launch("opened"), True),
        (_launch("started"), True),
        (_launch("failed", stage="window", detail="no"), False),
        (_launch("ended", exit_code=0), False),
        # an item's launch is read on past overdue: a claim may still arrive (spec 10)
        (_launch("started", age=120, overdue=True), True),
        (_launch("opened", age=599), True),
        (_launch("opened", age=600), False),
        (_launch("started", item_state="claimed"), False),
        (_launch("opened", item_state="declined"), False),
        (_launch("opening", test=True), True),
        (_launch("opened", test=True), True),
        (_launch("opened", test=True, age=599), True),
        (_launch("opened", test=True, age=600), False),
        # a test waits for no claim: once it has started it is followed for its first 60 seconds,
        # so that a Claude Code that ends at once shows, and it is done once it is overdue
        (_launch("started", test=True), True),
        (_launch("started", test=True, age=59), True),
        (_launch("started", test=True, age=60), False),
        (_launch("opened", test=True, age=91, overdue=True), False),
        (_launch("failed", test=True, stage="agent", detail="no"), False),
        (_launch("ended", test=True, exit_code=0), False),
        (None, False),
    ],
)
def test_following_says_whether_the_page_reads_a_launch_again(
    launch: dict[str, Any] | None, followed: bool
) -> None:
    assert node("following", [launch]) is followed


# ------------------------------------------------------------------------------- the section


def test_the_section_draws_the_form_as_the_server_serves_it() -> None:
    """A heading, the file's fault at the head with what to do, and a row for each field: its
    label tied to its control, its help under the label and tied to the control, a select whose
    first choice is empty and reads Default for a field with choices, a text field for the rest,
    and a refused save's sentence under the field it names. A text field with suggestions, the
    model's, names a list of them, so the browser offers each and still takes any other text; it
    does not turn the browser's offers off, which in some browsers hides the list too. No help
    line and no suggestion is kept in the script: the server sends each."""
    script = _static_file("agents.js")
    section = _function(script, "section")
    _in_order(
        section,
        "h('h2', { id: 'set-group-agents', className: 'title app-set__head' }, 'Agents'),",
        "form && form.fileError ? h('div', { className: 'app-set__notice' },",
        "h('p', { className: 'caption app-set__error' }, form.fileError),",
        "h('p', { className: 'caption' },",
        f"'{FIX_FILE}'))",
        "form.fields.map(function (field) { return row(field, redraw); }),",
        "actions(form, redraw)",
    )
    _in_order(_function(script, "actions"), "'Save'),", "'Test'),")
    row = _function(script, "row")
    for part in (
        "h('label', { className: 'body app-set__label', htmlFor: id }, field.label),",
        "h('p', { id: id + '-help', className: 'caption app-set__what' }, field.help)),",
        "error ? h('p', { id: id + '-error', className: 'caption app-set__error' }, error) : null",
        "var error = state.error && state.error.name === field.name ? state.error.sentence : null;",
    ):
        assert part in row, part
    control = _function(script, "control")
    for part in (
        "id: id, className: 'control app-field app-agents__",
        "'aria-describedby': id + '-help' + (error ? ' ' + id + '-error' : ''),",
        "if (field.choices) {",
        "h('option', { value: '' }, 'Default'),",
        "field.choices.map(function (choice) {",
        "type: 'text',",
        "value: held(field),",
        "text.autoComplete = 'off';",
        "return h('input', text);",
        "return h(React.Fragment, null,",
        "h('input', Object.assign({ list: id + '-list' }, text)),",
        "h('datalist', { id: id + '-list' },",
        "field.suggestions.map(function (suggestion) {",
        "return h('option', { key: suggestion, value: suggestion });",
    ):
        assert part in control, part
    _in_order(
        control,
        "if (field.choices) {",
        "var text = Object.assign({ type: 'text', spellCheck: false }, props);",
        "if (!field.suggestions) {",
    )
    assert "'opus'" not in script
    assert "Empty for Claude Code's own default." not in script
    assert "Fairband adds the launcher's words at the end." not in script


def test_save_sends_the_edits_alone_and_a_refusal_goes_to_its_field() -> None:
    """Save is off with no edit and while a save is in flight, except where the server cannot use
    the file, when a save writes it again. It sends ``edits`` alone as ``changes``. Taken, the
    form is the answer and the draft is cleared; refused, the server's "<name>: <rule>" stands
    under the field it names, or, where it names none, "Not saved: <the server's sentence>."
    beside Save, as the valuation settings say it (FairbandPage.refusal); a save that fails on the
    network is "Not saved: <the error>." there too."""
    script = _static_file("agents.js")
    actions = _function(script, "actions")
    assert "var changed = Object.keys(edits(form, state.draft)).length > 0;" in actions
    assert (
        "type: 'submit', variant: 'primary', "
        "disabled: state.saving || (!changed && !form.fileError)"
    ) in actions
    section = _function(script, "section")
    assert "onSubmit: function (event) { event.preventDefault(); save(redraw); }" in section
    save = _function(script, "save")
    for part in (
        "P.api.put('/api/launch-settings', { changes: edits(state.form, state.draft) })",
        "state.form = r.body;",
        "state.draft = {};",
        "var detail = P.refusalDetail(r);",
        "var cut = detail.indexOf(': ');",
        "var name = cut > 0 ? detail.slice(0, cut) : SAVE;",
        "state.error = named(name) ? { name: name, sentence: detail }",
        ": { name: SAVE, sentence: P.refusal('Not saved', r) };",
        "state.error = { name: SAVE, sentence: 'Not saved: ' + err.message + '.' };",
    ):
        assert part in save, part
    assert "detailOf" not in script
    assert save.index("if (r.ok) {") < save.index("state.draft = {};")
    assert "state.error && state.error.name === SAVE ? state.error.sentence : null;" in actions


def test_the_windows_terminal_line_fills_the_draft_and_saves_nothing() -> None:
    """The button shows only where the server suggests a line, in the window command's row; it
    puts the line in the window command's draft for Save to send, and posts nothing."""
    script = _static_file("agents.js")
    row = _function(script, "row")
    assert "field.name === WINDOW && state.form.suggested !== null ? h(F.Button, {" in row
    assert "'Use the Windows Terminal line')" in row
    assert "onClick: function () { useSuggested(redraw); }" in row
    suggested = _function(script, "useSuggested")
    assert "setDraft(named(WINDOW), state.form.suggested);" in suggested
    assert "P.api" not in suggested and "fetch" not in suggested
    assert "var WINDOW = 'window_command';" in script


def test_test_is_off_while_an_edit_is_unsaved_or_launching_is_not_ready() -> None:
    """A test runs the saved values, so Test is off while the form holds a change, and while
    launching is not set up; and while its own post is in flight, so a second press opens no
    second window."""
    actions = _function(_static_file("agents.js"), "actions")
    assert "disabled: changed || !form.ready || state.testing," in actions
    assert "onClick: function () { startTest(redraw); }" in actions


def test_test_posts_a_test_launch_and_follows_it() -> None:
    """Test posts ``{test: true}``; a 201 is the launch, then read every 2 seconds while the page
    follows it, its line drawn each time. One timer at most: it is cleared before a new test and
    whenever the launch is no longer followed, and an answer for an earlier test is dropped. A
    refusal's sentence shows where the test's line shows, in the error style; while the post is
    in flight the line is the opening one. A read of the launch that fails says so in the error
    style."""
    script = _static_file("agents.js")
    assert "var READ_MS = 2000;" in script
    start = _function(script, "startTest")
    _in_order(
        start,
        "stop();",
        "P.api.post('/api/launches', { test: true })",
        "state.launch = r.body;",
        "follow(redraw);",
    )
    assert "state.testError = P.refusalDetail(r);" in start
    follow = _function(script, "follow")
    _in_order(
        follow,
        "stop();",
        "if (!P.following(state.launch)) return;",
        "timer = setTimeout(function () {",
        "P.getJson('/api/launches/' + id)",
        "if (!state.launch || state.launch.id !== id) return;",
        "state.launch = launch;",
        "follow(redraw);",
        "redraw();",
        "state.testError = 'The test\\'s launch could not be read: ' + err.message + '.';",
        "}, READ_MS);",
    )
    stop = _function(script, "stop")
    assert "clearTimeout(timer);" in stop and "timer = null;" in stop
    actions = _function(script, "actions")
    _in_order(
        actions,
        "var line = state.testing ? testLine({ state: 'opening' })",
        ": state.testError ? { text: state.testError, failed: true }",
        ": state.launch ? testLine(state.launch) : null;",
        "'caption app-agents__line' + (line.failed ? ' app-set__error' : '')",
    )


def test_the_section_reads_only_what_the_server_sends(tmp_path: Path) -> None:
    """Every name the script's code reads off the form, a field or a launch is one the server
    sends; its comments, which name launch.json, are left out."""
    script = re.sub(r"/\*.*?\*/", "", _static_file("agents.js"), flags=re.DOTALL)
    form = form_json(read_launch_file(tmp_path), None)
    made = datetime(2026, 11, 16, 10, tzinfo=UTC)
    row = LaunchRow(
        id=7,
        item_id=None,
        agent="claude",
        state="opened",
        stage=None,
        detail=None,
        exit_code=None,
        created_at=made,
        updated_at=made,
    )
    launch = launch_json(row, None, made)
    for pattern, sent in (
        (r"\bform\.(\w+)", set(form)),
        (r"\bfield\.(\w+)", set(form["fields"][0])),
        (r"\blaunch\.(\w+)", set(launch)),
    ):
        read = set(re.findall(pattern, script))
        assert read and read <= sent, read - sent


def test_the_section_hangs_its_helpers_on_the_page() -> None:
    script = _static_file("agents.js")
    assert (
        "P.agents = { load: load, section: section, edits: edits, testLine: testLine };"
    ) in script
    load = _function(script, "load")
    assert "P.getJson('/api/launch-settings')" in load
    assert "if (request !== latest) return;" in load
    assert "following: following" in _static_file("app.js")


# --------------------------------------------------------------------- the page around it


def test_settings_draws_the_section_after_its_own_view_and_loads_it_as_it_opens() -> None:
    """The section has its own read, so it is drawn after the form, the refused view or the load
    failure alike, through the Settings view's render."""
    script = _static_file("settings.js")
    view = _function(script, "View")
    assert "return h(React.Fragment, null, valuation(), P.agents.section(render));" in view
    valuation = _function(script, "valuation")
    assert "if (state.refused) return refusedView();" in valuation
    shown = script[script.index("P.onShow.settings = function () {") :]
    assert "P.agents.load(render);" in shown[: shown.index("};")]


def test_the_page_loads_agents_js_before_settings_js_and_styles_it_with_tokens() -> None:
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert scripts.index("app.js") < scripts.index("agents.js") < scripts.index("settings.js")
    assert "width: 32rem;" in _rule(".app-agents__text")
    assert "font-family: var(--font-mono);" in _rule(".app-agents__text")
    # The text field narrows to its column and never lays over the label: at 700px wide the
    # 32rem field ran left over "Claude Code command".
    assert "min-width: 0;" in _rule(".app-agents__text")
    assert _rule(".app-agents .app-set__fields") == "align-self: stretch;"
    assert _rule(".app-agents__line") == "flex-basis: 100%; margin: 0;"
    rules = html[html.index("  .app-agents {") : html.index("  .app-agents__line {")]
    assert "#" not in rules, "a raw colour"
    assert "border-color: var(--caution);" in rules
