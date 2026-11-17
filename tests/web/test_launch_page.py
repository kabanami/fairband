"""The request button's launch (spec 2026-11-16 agent launch, 10): in the drawer and on the company
page, Request research's menu ticks Open Claude Code where launching is set up, a post taken then
opens a window for its item, and the line under the button says where the launch is, with Open
Claude Code or Open again after it. ``launchLine``, ``asking`` and ``requestResearch``'s drawing
run in node (``support.page``) and the tests read what they return; the menu, the posts, the
following and its clears, company.js's calls and the page's styles are read from the files, as
``tests/web/test_agents_page.py`` reads the Agents section's; ``tests/web/test_launch_following.py``
runs the posts and the following with a fetch and timers of its own."""

import re
from datetime import UTC, datetime
from typing import Any

import pytest
from support.page import NODE, classed, elements, node, text
from support.web import _static_file

from fairband.store.launches import LaunchRow
from fairband.web.launch_api import launch_json

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

AGENT = "claude-opus-5-5"
CHECK = "Check Settings, Agents."


def _function(script: str, name: str) -> str:
    """The text of the script's ``function <name>(``, to its closing brace."""
    start = script.index(f"  function {name}(")
    return script[start : script.index("\n  }\n", start)]


def _in_order(text: str, *parts: str) -> None:
    """Each part is in ``text``, each after the one before it."""
    at = [text.index(part) for part in parts]
    assert at == sorted(at), [parts[i] for i in range(len(parts) - 1) if at[i] > at[i + 1]]


def _code(script: str) -> str:
    """A script without its comments."""
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", script, flags=re.DOTALL)


def _rule(selector: str) -> str:
    """The declarations of the page's rule for ``selector``."""
    pattern = rf"\n  {re.escape(selector)} \{{(.*?)\}}"
    found = re.search(pattern, _static_file("index.html"), re.DOTALL)
    assert found is not None, selector
    return " ".join(found.group(1).split())


def _launch(
    state: str,
    *,
    launch_id: int = 7,
    item_id: int = 12,
    overdue: bool = False,
    stage: str | None = None,
    detail: str | None = None,
    exit_code: int | None = None,
) -> dict[str, Any]:
    """A launch of a work item as ``GET /api/launches/{id}`` answers it, its item pending."""
    return {
        "id": launch_id,
        "itemId": item_id,
        "test": False,
        "agent": "claude",
        "state": state,
        "stage": stage,
        "detail": detail,
        "exitCode": exit_code,
        "createdAt": "2026-11-16T10:00:00+00:00",
        "updatedAt": "2026-11-16T10:00:00+00:00",
        "ageSeconds": 95 if overdue else 10,
        "overdue": overdue,
        "itemState": "pending",
        "claimedBy": None,
    }


def _item(
    state: str = "pending", launch: dict[str, Any] | None = None, *, item_id: int = 12
) -> dict[str, Any]:
    """The company detail's open work item, with its newest launch."""
    return {
        "id": item_id,
        "state": state,
        "mode": "full report",
        "claimedBy": AGENT if state == "claimed" else None,
        "createdAt": "2026-11-16T09:59:00+00:00",
        "launch": launch,
    }


def _ask(**changes: Any) -> dict[str, Any]:
    """A request as ``asking`` makes it, with ``changes``."""
    return {
        "symbol": "AAPL",
        "open": False,
        "mode": "full report",
        "note": "",
        "error": None,
        "posting": False,
        "launch": True,
        "opening": False,
        "followed": None,
        "timer": None,
        "misses": 0,
        "round": 0,
    } | changes


# ------------------------------------------------------------------------------- the line

LINES = [
    pytest.param(_item("claimed"), f"Requested · claimed by {AGENT}", False, None, id="claimed"),
    pytest.param(
        _item("claimed", _launch("started")),
        f"Requested · claimed by {AGENT}",
        False,
        None,
        id="claimed-started",
    ),
    pytest.param(
        _item("claimed", _launch("failed", stage="agent", detail="`claude` was not found")),
        f"Requested · claimed by {AGENT}",
        False,
        None,
        id="claimed-failed",
    ),
    pytest.param(_item(), "Requested · pending", False, "open", id="pending"),
    pytest.param(
        _item(launch=_launch("opening")), "Requested · opening a window…", False, None, id="opening"
    ),
    pytest.param(
        _item(launch=_launch("failed", stage="window", detail="`wt.exe` was not found")),
        f"Could not open the window: `wt.exe` was not found. {CHECK}",
        True,
        "again",
        id="failed-window",
    ),
    pytest.param(
        _item(launch=_launch("opened")),
        "Requested · the window opened, Claude Code is starting…",
        False,
        None,
        id="opened",
    ),
    pytest.param(
        _item(launch=_launch("opened", overdue=True)),
        "The window opened, but nothing in it reported after 90 seconds. Check the window.",
        True,
        "again",
        id="opened-overdue",
    ),
    pytest.param(
        _item(
            launch=_launch(
                "failed",
                stage="agent",
                detail="`claude-nope` was not found on the path of a login shell",
            )
        ),
        "The window opened, but Claude Code did not start: `claude-nope` was not found on the "
        f"path of a login shell. {CHECK}",
        True,
        "again",
        id="failed-agent",
    ),
    pytest.param(
        _item(launch=_launch("started")),
        "Requested · Claude Code started, not claimed yet",
        False,
        None,
        id="started",
    ),
    pytest.param(
        _item(launch=_launch("started", overdue=True)),
        "Claude Code started, but no agent claimed this request after 90 seconds. Check the "
        "window.",
        True,
        "again",
        id="started-overdue",
    ),
    pytest.param(
        _item(launch=_launch("ended", exit_code=1)),
        "Claude Code ended before it claimed this request (exit code 1).",
        True,
        "again",
        id="ended",
    ),
]


@pytest.mark.parametrize("ready", [True, False], ids=["ready", "not-ready"])
@pytest.mark.parametrize(("item", "line", "failed", "action"), LINES)
def test_the_line_says_where_the_items_launch_is(
    item: dict[str, Any], line: str, failed: bool, action: str | None, ready: bool
) -> None:
    """Spec 10's line for the open item and its newest launch, word for word: a claim whatever
    the launch, a failure's and the two overdue lines in the error style with Open again, and
    Open Claude Code on a pending item with no launch only where launching is set up."""
    wanted = None if action == "open" and not ready else action
    assert node("launchLine", [item, ready]) == {"text": line, "failed": failed, "action": wanted}


@pytest.mark.parametrize(("item", "line", "failed", "action"), LINES)
def test_the_words_are_the_line_without_requested(
    item: dict[str, Any], line: str, failed: bool, action: str | None
) -> None:
    """``launchWords``, which the Inbox view's row shows under its state word (B-210): the line
    without its first word Requested, a failure's sentence whole."""
    words = line.removeprefix("Requested · ")
    assert (words == line) is failed
    assert node("launchWords", [item, True]) == {"text": words, "failed": failed, "action": action}


def test_no_open_item_has_no_line() -> None:
    assert node("launchLine", [None, True]) is None
    assert node("launchWords", [None, True]) is None


def test_the_item_a_line_is_drawn_from() -> None:
    """``lineItem``: an item with an opening launch while a launch's post is in flight, whatever
    the item, before the item is read again too; else the item, with the launch the page follows
    in place of its own where it is that item's."""
    opening = {"state": "pending", "launch": {"state": "opening"}}
    item = _item(launch=_launch("opened"))
    for held in (None, _item(), item):
        assert node("lineItem", [_ask(opening=True), held]) == opening
    assert node("lineItem", [_ask(), None]) is None
    assert node("lineItem", [_ask(), item]) == item
    followed = _launch("started")
    assert node("lineItem", [_ask(followed=followed), item]) == item | {"launch": followed}
    other = _launch("started", item_id=13)
    assert node("lineItem", [_ask(followed=other), item]) == item
    assert node("lineItem", [_ask(followed=followed), None]) is None


def test_the_line_reads_only_what_the_server_sends() -> None:
    """Every name ``launchWords`` reads off the item or its launch is one the detail read sends."""
    script = _code(_function(_static_file("app.js"), "launchWords"))
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
    for pattern, sent in (
        (r"\bitem\.(\w+)", set(_item())),
        (r"\blaunch\.(\w+)", set(launch_json(row, None, made))),
    ):
        read = set(re.findall(pattern, script))
        assert read and read <= sent, read - sent


# -------------------------------------------------------------------- the line as drawn


def _drawn(ask: dict[str, Any], item: dict[str, Any] | None, ready: bool) -> Any:
    """What ``requestResearch`` draws for the request and the open item, with no handlers."""
    return node("requestResearch", [ask, item, None, None, ready])


def _lines(tree: Any) -> list[dict[str, Any]]:
    return classed(tree, "app-requested") + classed(tree, "app-request__error")


def _request_button(tree: Any) -> dict[str, Any]:
    [button] = [e for e in elements(tree) if e["props"].get("children") == ["Request research"]]
    return button


def test_the_line_has_its_button_only_where_launching_is_set_up() -> None:
    """Open Claude Code and Open again are small quiet buttons after the line's text, drawn only
    where launching is set up; a failure's line takes the request's error line's class."""
    tree = _drawn(_ask(), _item(), True)
    [line] = _lines(tree)
    assert line["props"]["className"] == "caption app-requested"
    assert line["props"]["children"][0] == "Requested · pending"
    [button] = classed(line, "app-request__open")
    assert (button["props"]["size"], button["props"]["variant"]) == ("sm", "quiet")
    assert text(button) == "Open Claude Code"
    assert not classed(_drawn(_ask(), _item(), False), "app-request__open")

    failed = _item(launch=_launch("ended", exit_code=1))
    [line] = _lines(_drawn(_ask(), failed, True))
    assert line["props"]["className"] == "caption app-request__error"
    [button] = classed(line, "app-request__open")
    assert text(button) == "Open again"
    [line] = _lines(_drawn(_ask(), failed, False))
    assert line["props"]["className"] == "caption app-request__error"
    assert not classed(line, "app-request__open")

    [line] = _lines(_drawn(_ask(), _item(launch=_launch("started")), True))
    assert not classed(line, "app-request__open")
    assert _lines(_drawn(_ask(), None, True)) == []


def test_while_a_launch_is_posted_the_line_says_a_window_is_opening() -> None:
    """While the launch's post is in flight the line is the opening one whatever the item's
    launch, before the item has been read again too, with no button; Request research is off."""
    for item in (None, _item(), _item(launch=_launch("failed", stage="window", detail="no"))):
        tree = _drawn(_ask(opening=True), item, True)
        [line] = _lines(tree)
        assert line["props"]["className"] == "caption app-requested"
        assert text(line) == "Requested · opening a window…"
        assert _request_button(tree)["props"]["disabled"] is True
    assert _request_button(_drawn(_ask(), None, True))["props"]["disabled"] is False
    assert _request_button(_drawn(_ask(), _item(), True))["props"]["disabled"] is True


def test_the_line_reads_the_followed_launch_of_the_open_item() -> None:
    """The launch the page follows replaces the item's own on the line while it is that item's;
    another item's is not read."""
    followed = _launch("started")
    [line] = _lines(_drawn(_ask(followed=followed), _item(launch=_launch("opened")), True))
    assert text(line) == "Requested · Claude Code started, not claimed yet"
    other = _launch("started", item_id=13)
    [line] = _lines(_drawn(_ask(followed=other), _item(launch=_launch("opened")), True))
    assert text(line) == "Requested · the window opened, Claude Code is starting…"


# -------------------------------------------------------------------- the menu and the posts


def test_asking_starts_with_the_box_ticked_and_no_launch() -> None:
    assert node("asking", ["AAPL"]) == _ask()


def test_the_menu_ticks_open_claude_code_only_where_launching_is_set_up() -> None:
    """The checkbox is a row in the menu's style under the note line and above Post, ticked from
    the request, drawn only where launching is set up; the menu takes ``ready`` from Request
    research and hands it to the post."""
    script = _static_file("app.js")
    menu = _function(script, "RequestMenu")
    assert "var ready = props.ready;" in menu
    _in_order(
        menu,
        "'NOTE'",
        "ready ? h('div', { className: 'fb-menu__sec app-request__launch' },",
        "h('label', { className: 'fb-menu__row control' },",
        "type: 'checkbox', checked: ask.launch,",
        "onChange: function () { ask.launch = !ask.launch; redraw(); }",
        "h('span', null, 'Open Claude Code')",
        "'Post')",
    )
    assert "postRequest(ask, redraw, after, ready);" in menu
    ask = _function(script, "requestResearch")
    assert "h(RequestMenu, { ask: ask, redraw: redraw, after: after, ready: ready })" in ask


def test_a_post_taken_with_the_box_ticked_opens_a_window_for_its_item() -> None:
    """The item is posted as before; where the post was taken, launching is set up, the box is
    ticked and the request was not stopped while the post was in flight, its answer's id goes to
    ``openLaunch``, which reads the company again itself, so ``after`` runs once for a click
    either way (``tests/web/test_launch_following.py`` runs it)."""
    post = _function(_static_file("app.js"), "postRequest")
    _in_order(
        post,
        "var round = ask.round;",
        "api.post('/api/inbox', { symbol: ask.symbol, mode: ask.mode, note: ask.note.trim() })",
        "posted = r.body.id;",
        ".catch(function (err) { ask.error = err.message; })",
        "ask.open = false;",
        "if (posted !== null && ready && ask.launch && round === ask.round) {",
        "openLaunch(ask, posted, redraw, after);",
        "} else {",
        "after();",
    )
    assert post.count("after()") == 1


def test_open_launch_posts_a_launch_and_a_409_shows_no_error() -> None:
    """``openLaunch`` stops any following, posts the item's launch and, once the post ends, reads
    the company again once and follows the launch a 201 gave. A 409, the item no longer pending or
    a launch in flight, sets no error: the company read again draws the claim or the launch. Any
    other refusal's sentence is the request's error, and a post that fails on the network says
    that the window was not opened."""
    launch = _function(_static_file("app.js"), "openLaunch")
    _in_order(
        launch,
        "if (ask.opening) return;",
        "stopLaunch(ask);",
        "ask.followed = null;",
        "ask.opening = true;",
        "ask.error = null;",
        "redraw();",
        "var round = ask.round;",
        "api.post('/api/launches', { itemId: itemId })",
        "if (r.ok) ask.followed = r.body;",
        "else if (r.status !== 409) ask.error = refusalDetail(r);",
        "}, function (err) {",
        "ask.error = 'The window was not opened: ' + err.message + '.';",
        "ask.opening = false;",
        "after();",
        "if (round === ask.round) followLaunch(ask, redraw, after);",
    )
    assert launch.count("after()") == 1
    assert launch.count("409") == 1


def test_the_buttons_open_a_window_for_the_open_item() -> None:
    line = _function(_static_file("app.js"), "requested")
    _in_order(
        line,
        "var line = launchLine(lineItem(ask, item), ready);",
        "className: line.failed ? 'caption app-request__error' : 'caption app-requested'",
        "line.text,",
        "ready && line.action ? h(F.Button, {",
        "size: 'sm', variant: 'quiet', className: 'app-request__open',",
        "onClick: function () { openLaunch(ask, item.id, redraw, after); }",
        "line.action === 'open' ? 'Open Claude Code' : 'Open again'",
    )


# ---------------------------------------------------------------------------- the following


def test_the_following_reads_the_launch_every_2_seconds_and_reads_the_company_once_it_ends() -> (
    None
):
    """One timer for a request: while the followed launch is followed (FairbandPage.following) it
    is read 2 seconds after the last answer, each answer replacing the followed launch and drawn;
    once an answer is no longer followed, the company is read again once. An answer from a
    following stopped meanwhile is dropped; a read that fails is tried again, and the 30th in a
    row ends the following and reads the company again (``tests/web/test_launch_following.py``
    runs it)."""
    script = _static_file("app.js")
    assert "var LAUNCH_READ_MS = 2000;" in script
    assert "var LAUNCH_MISSES = 30;" in script
    follow = _function(script, "followLaunch")
    _in_order(
        follow,
        "var launch = ask.followed;",
        "if (ask.timer !== null || !following(launch)) return;",
        "var round = ask.round;",
        "ask.timer = setTimeout(function () {",
        "getJson('/api/launches/' + launch.id).then(function (got) {",
        "}, function (err) {",
        "}, LAUNCH_READ_MS);",
    )
    answer = follow[follow.index("function (got) {") : follow.index("}, function (err) {")]
    failed = follow[follow.index("}, function (err) {") : follow.index("}, LAUNCH_READ_MS);")]
    _in_order(
        answer,
        "if (round !== ask.round) return;",
        "ask.timer = null;",
        "ask.misses = 0;",
        "unread(ask);",
        "ask.followed = got;",
        "if (following(got)) followLaunch(ask, redraw, after);",
        "else after();",
        "redraw();",
    )
    _in_order(
        failed,
        "if (round !== ask.round) return;",
        "ask.timer = null;",
        "ask.misses++;",
        "if (ask.misses < LAUNCH_MISSES) {",
        "ask.error = UNREAD + err.message + '. Trying again.';",
        "followLaunch(ask, redraw, after);",
        "} else {",
        "ask.error = UNREAD + err.message + '. Reload the page.';",
        "after();",
        "redraw();",
    )
    assert failed.count("after()") == 1
    assert follow.count("after()") == 2
    stop = _function(script, "stopLaunch")
    for part in (
        "ask.round++;",
        "clearTimeout(ask.timer);",
        "ask.timer = null;",
        "ask.misses = 0;",
    ):
        assert part in stop, part


def test_the_following_stops_when_the_drawer_closes_or_another_company_shows() -> None:
    """The timer is cleared when the drawer closes, when it turns to another company, and when
    the company page starts to read another company, before the read, so a read that fails leaves
    no following of the company shown before (``tests/web/test_company_page.py`` pins the order
    of the page's read)."""
    script = _static_file("app.js")
    assert "if (state.request) stopLaunch(state.request);" in _function(script, "close")
    _in_order(
        _function(script, "open"),
        "if (d && d.symbol === row.ticker && !d.error) return;",
        "if (state.request && state.request.symbol !== row.ticker) stopLaunch(state.request);",
        "getJson('/api/companies/' + encodeURIComponent(row.ticker))",
    )
    load = _code(_function(_static_file("company.js"), "load"))
    _in_order(
        load,
        "var want = P.company;",
        "if (state.request && state.request.symbol !== want.symbol) P.stopLaunch(state.request);",
        "(whole ? read(company) : Promise.resolve(state.detail))",
    )
    assert load.count("P.stopLaunch(") == 1


def test_a_view_that_loads_with_a_launch_in_flight_follows_it() -> None:
    """Each read of the drawer's company and of the company page's goes through ``followItem``:
    the followed launch goes once the read holds no open item, another item or a newer launch,
    or no following runs; and where none runs and the open item's launch is followed, the
    following starts from it."""
    script = _static_file("app.js")
    item = _function(script, "followItem")
    _in_order(
        item,
        "var held = ask.followed;",
        "if (held && (ask.timer === null || !item || held.itemId !== item.id ||",
        "(item.launch && item.launch.id > held.id))) {",
        "stopLaunch(ask);",
        "ask.followed = null;",
        "if (ask.timer !== null || ask.opening || !item || !following(item.launch)) return;",
        "unread(ask);",
        "ask.followed = item.launch;",
        "followLaunch(ask, redraw, after);",
    )
    landed = _function(script, "landed")
    _in_order(
        landed,
        "state.drawer = { symbol: symbol, body: body, loading: false, error: null };",
        "followItem(asked(body.result.symbol), body.item, render, reread(body.result.symbol));",
    )
    assert "landed(row.ticker, body);" in _function(script, "open")
    assert "landed(symbol, body);" in _function(script, "reloadDetail")
    assert "return function () { reloadDetail(symbol); };" in _function(script, "reread")
    _in_order(
        _function(_static_file("company.js"), "shown"),
        "state.request = P.asking(state.symbol);",
        "P.followItem(state.request, state.detail.item, render, load);",
        "render();",
    )


# ------------------------------------------------------------------------- the page around it


def test_the_drawer_and_the_company_page_pass_whether_launching_is_set_up() -> None:
    sections = _function(_static_file("app.js"), "sections")
    assert "requestResearch(ask, body.item, render, reread(r.symbol), body.launchReady)" in (
        sections
    )
    company = _code(_static_file("company.js"))
    call = "P.requestResearch(ask, d.item, render, load, d.launchReady)"
    assert company.count("P.requestResearch(") == 1 == company.count(call)
    assert call in _function(company, "head")


def test_the_page_hangs_the_launch_helpers_on_fairband_page() -> None:
    script = _static_file("app.js")
    exposed = script[script.index("window.FairbandPage = {") :]
    exposed = exposed[: exposed.index("};")]
    for name in (
        "requestResearch: requestResearch",
        "launchLine: launchLine",
        "launchWords: launchWords",
        "lineItem: lineItem",
        "openLaunch: openLaunch",
        "stopLaunch: stopLaunch",
        "followItem: followItem",
    ):
        assert name in exposed, name


def test_the_checkbox_and_the_buttons_are_styled_with_tokens() -> None:
    assert _rule(".app-request__launch") == "margin-top: var(--space-2);"
    assert _rule(".app-request__open") == "margin-left: var(--space-2);"
