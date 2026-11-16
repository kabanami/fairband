"""The Inbox view's launch (B-210; spec 2026-11-16 agent launch, 10): a pending item's row has
Open Claude Code where launching is set up, and under its state word what the drawer's line says
of the item's launch, with Open again after a failure. ``launchParts``, which inbox.js hangs on
the page, runs in node (``support.page``) and the tests read what it returns; the row, the
view's reads, its following and the styles are read from the files, as
``tests/web/test_launch_page.py`` reads the drawer's."""

import re
from typing import Any

import pytest
from support.page import NODE, STATIC, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

AGENT = "claude-opus-5-5"
INBOX = STATIC / "inbox.js"


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


def _launch(
    state: str, *, launch_id: int = 7, item_id: int = 12, exit_code: int | None = None
) -> dict[str, Any]:
    """A launch of a work item as ``GET /api/launches/{id}`` answers it, its item pending."""
    return {
        "id": launch_id,
        "itemId": item_id,
        "test": False,
        "agent": "claude",
        "state": state,
        "stage": None,
        "detail": None,
        "exitCode": exit_code,
        "createdAt": "2026-11-16T10:00:00+00:00",
        "updatedAt": "2026-11-16T10:00:00+00:00",
        "ageSeconds": 10,
        "overdue": False,
        "itemState": "pending",
        "claimedBy": None,
    }


def _item(state: str = "pending", launch: dict[str, Any] | None = None) -> dict[str, Any]:
    """A work item as ``GET /api/inbox`` lists it, with its newest launch."""
    return {
        "id": 12,
        "symbol": "AAPL",
        "mode": "full report",
        "note": "",
        "snapshotId": 3,
        "origin": "expiry",
        "postedBy": "system",
        "postedActor": None,
        "postedClient": None,
        "postedAt": "2026-11-16T09:59:00+00:00",
        "state": state,
        "claimedBy": AGENT if state == "claimed" else None,
        "claimedAt": None,
        "reportId": None,
        "reason": None,
        "finishedAt": None,
        "expiryValidUntil": "2026-11-15",
        "reportRevision": None,
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


def _parts(item: dict[str, Any], ask: dict[str, Any], ready: bool) -> dict[str, Any]:
    parts: dict[str, Any] = node("inbox.launchParts", [item, ask, ready], INBOX)
    return parts


# --------------------------------------------------------------------------- the row's parts


def test_a_pending_item_has_open_claude_code_only_where_launching_is_set_up() -> None:
    """A pending item with no launch, an expiry item say: no words under the state, which says
    pending already, and the button, small, named for its company as Decline is."""
    parts = _parts(_item(), _ask(), True)
    assert parts["words"] is None
    button = parts["button"]["props"]
    assert (button["size"], button["className"]) == ("sm", "app-inbox__open")
    assert button["aria-label"] == "Open Claude Code for the work item for AAPL"
    assert text(parts["button"]) == "Open Claude Code"
    assert _parts(_item(), _ask(), False) == {"words": None, "button": None}


def test_a_launch_in_flight_says_where_it_is_and_has_no_button() -> None:
    parts = _parts(_item(launch=_launch("started")), _ask(), True)
    assert parts["words"]["props"]["className"] == "caption app-inbox__why"
    assert text(parts["words"]) == "Claude Code started, not claimed yet"
    assert parts["button"] is None


def test_a_failed_launch_says_why_in_the_error_style_with_open_again() -> None:
    failed = _item(launch=_launch("ended", exit_code=1))
    parts = _parts(failed, _ask(), True)
    assert parts["words"]["props"]["className"] == "caption app-inbox__why app-inbox__failed"
    assert text(parts["words"]) == (
        "Claude Code ended before it claimed this request (exit code 1)."
    )
    assert text(parts["button"]) == "Open again"
    assert parts["button"]["props"]["aria-label"] == (
        "Open Claude Code again for the work item for AAPL"
    )
    parts = _parts(failed, _ask(), False)
    assert text(parts["words"]).startswith("Claude Code ended")
    assert parts["button"] is None


def test_while_a_launch_is_posted_the_row_says_a_window_is_opening() -> None:
    for item in (_item(), _item(launch=_launch("ended", exit_code=1))):
        parts = _parts(item, _ask(opening=True), True)
        assert parts["words"]["props"]["className"] == "caption app-inbox__why"
        assert text(parts["words"]) == "opening a window…"
        assert parts["button"] is None


def test_the_row_reads_the_followed_launch_of_its_item() -> None:
    """The launch the view follows replaces the item's own while it is that item's."""
    item = _item(launch=_launch("opened"))
    parts = _parts(item, _ask(followed=_launch("started")), True)
    assert text(parts["words"]) == "Claude Code started, not claimed yet"
    parts = _parts(item, _ask(followed=_launch("started", item_id=13)), True)
    assert text(parts["words"]) == "the window opened, Claude Code is starting…"


@pytest.mark.parametrize("state", ["claimed", "done", "declined", "dropped"])
def test_an_item_that_is_not_pending_has_no_launch_parts(state: str) -> None:
    """A claimed item's row says claimed and by whom already; a closed item has no launch."""
    item = _item(state, _launch("started"))
    assert _parts(item, _ask(opening=True), True) == {"words": None, "button": None}


# ------------------------------------------------------------------------------- the view


def test_the_row_draws_the_parts_and_a_refused_launchs_sentence() -> None:
    """The words stand under the state word, the button before Decline, and a launch's refusal,
    the server's sentence, on a line under the row as a refused decline's does."""
    row = _function(_static_file("inbox.js"), "row")
    _in_order(
        row,
        "var ask = item.state === 'pending' ? asked(item) : null;",
        "var parts = launchParts(item, ask, state.ready);",
        "h('td', { className: 'body app-inbox__wrap' }, item.state,",
        "parts.words),",
        "h('td', null, parts.button, open && !declining ? h(F.Button, {",
        "state.errors[item.id] ? refused(state.errors[item.id]) : null,",
        "ask && ask.error ? refused(ask.error) : null);",
    )
    assert "P.inbox = { launchParts: launchParts };" in _static_file("inbox.js")


def test_the_button_posts_the_items_launch_as_the_drawers_does() -> None:
    script = _static_file("inbox.js")
    assert "P.openLaunch(asked(item), item.id, redraw, reread(item));" in _function(script, "open")
    assert "onClick: function () { open(item); }" in _function(script, "launchParts")
    asked = _function(script, "asked")
    assert "state.asks[item.id] || (state.asks[item.id] = P.asking(item.symbol))" in asked
    # once the post ends, and once a following ends, the drawer and the view read again
    _in_order(
        _function(script, "reread"),
        "P.reloadDetail(item.symbol);",
        "if (!panel.hidden) load();",
    )


def test_each_read_follows_the_pending_items_launches_and_forgets_the_rest() -> None:
    """The view's own read keeps whether launching is set up; it and the header's read follow
    each pending item's launch while that is in flight (``followItem``), and an item that is no
    longer pending stops its following."""
    script = _static_file("inbox.js")
    _in_order(
        _function(script, "load"),
        "state.items = body.items;",
        "state.ready = body.launchReady === true;",
        "P.countInbox(body.items);",
        "follow(body.items);",
    )
    _in_order(
        _function(script, "fromHeader"),
        "if (panel.hidden || state.loading) return;",
        "state.items = items;",
        "follow(items);",
        "render();",
    )
    _in_order(
        _function(script, "follow"),
        "if (item.state === 'pending') P.followItem(asked(item), item, redraw, reread(item));",
        "else forget(item.id);",
    )
    _in_order(
        _function(script, "forget"),
        "P.stopLaunch(state.asks[id]);",
        "delete state.asks[id];",
    )


def test_a_hidden_view_stops_every_following() -> None:
    """The following draws through ``redraw``: the view's draw while it shows; once it is hidden
    each request's following stops, and the read as the view opens again starts those still in
    flight."""
    _in_order(
        _function(_static_file("inbox.js"), "redraw"),
        "if (!panel.hidden) return render();",
        "Object.keys(state.asks).forEach(function (id) { P.stopLaunch(state.asks[id]); });",
    )


def test_the_rows_button_and_failure_are_styled_with_tokens() -> None:
    assert _rule(".app-inbox__open") == "margin-right: var(--space-2);"
    assert _rule(".app-inbox__failed") == "color: var(--caution);"
    html = _static_file("index.html")
    # the failure's colour wins over the muted caption's: its rule comes later
    assert html.index("  .app-inbox__why {") < html.index("  .app-inbox__failed {")
