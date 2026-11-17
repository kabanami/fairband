"""The Notes control and its box (the company page's design, 11.1): the word ``Notes`` in the quiet
button's look, with the count of the company's notes when it has one or more, at the left of the
drawer's top bar and in the company page's head before the watchlists control. A click opens a box
under it, in the frame of the watchlists popup: the company's notes newest first, each with its
text and its principal chip, which carries its day, in a list that scrolls under 240px, or ``No
notes yet.``; under the list Add a note as Details had it, its field, its button and the server's
sentence on a refusal, the text kept. The page's own scripts run in node after the bundle
(``support.page``), and the tests read the trees ``notesControl``, ``notesBox``, ``drawer`` and the
company page's ``head`` return; the shell around them, its reads, its write and its listeners, is
read as text."""

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support import page_answers as answers
from support.page import NODE, STATIC, classed, elements, node, text
from support.web import HEADER, _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

COMPANY = STATIC / "company.js"
DRAFT: dict[str, Any] = {"symbol": "ACME", "text": "", "error": None, "posting": False}
NOTES: list[dict[str, Any]] = [
    {
        "id": 7,
        "symbol": "ACME",
        "text": "Margins look peaked.\nWatch the second half.",
        "principal": "owner",
        "actor": None,
        "client": None,
        "at": "2026-11-16T09:30:00+00:00",
        "overrideId": None,
    },
    {
        "id": 3,
        "symbol": "ACME",
        "text": "The cycle gap is half, on segment margins.",
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "at": "2026-11-02T18:05:00+00:00",
        "overrideId": 12,
    },
]


def _box(**changes: Any) -> dict[str, Any]:
    """A box open on ACME with its two notes read and nothing typed, with ``changes``."""
    box: dict[str, Any] = {
        "symbol": "ACME",
        "notes": NOTES,
        "loading": False,
        "error": None,
        "draft": DRAFT,
    }
    return box | changes


def _drawn(box: dict[str, Any]) -> Any:
    return node("notesBox", [box])


def _one(tree: Any, name: str) -> dict[str, Any]:
    [found] = classed(tree, name)
    return found


def _chips(tree: Any) -> list[dict[str, Any]]:
    """The bundle's PrincipalChip elements, undrawn: their props as given."""
    return [e for e in elements(tree) if "principal" in e["props"]]


def _buttons(tree: Any, words: str) -> list[dict[str, Any]]:
    """The bundle Buttons of ``tree`` whose text is ``words``, undrawn: their props as given."""
    return [e for e in elements(tree) if e["props"].get("children") == [words]]


def _function(script: str, name: str) -> str:
    """The text of the script's ``function <name>(``, to its closing brace."""
    start = script.index(f"  function {name}(")
    return script[start : script.index("\n  }\n", start)]


def _in_order(within: str, *parts: str) -> None:
    """Each part is in ``within``, each after the one before it."""
    at = [within.index(part) for part in parts]
    assert at == sorted(at), parts


def _rule(selector: str) -> str:
    """The declarations of the page's one rule whose line opens with ``selector``, on one line."""
    css = _static_file("index.html")
    ends = [m.end() for m in re.finditer(r"(?m)^[ \t]*" + re.escape(selector), css)]
    assert len(ends) == 1, selector
    return " ".join(css[ends[0] : css.index("}", ends[0])].split())


# ---------------------------------------------------------------------------------- the control


def test_the_control_without_a_count_and_with_one() -> None:
    """A quiet small button: ``Notes`` for a company with no note, ``Notes 3`` with three."""
    for count, words in ((0, "Notes"), (None, "Notes"), (1, "Notes 1"), (3, "Notes 3")):
        control = node("notesControl", ["ACME", count])
        assert control["props"] == {
            "variant": "quiet",
            "size": "sm",
            "className": "app-notes-open",
            "children": [words],
        }


# ------------------------------------------------------------------------------------- the box


def test_the_box_lists_the_notes_newest_first(client: TestClient) -> None:
    """The read gives a company's notes newest first, and the box keeps that order: each note's
    text as written, then its principal chip with its principal, its actor and its time in the
    reader's offset, which the chip draws as the day. The list scrolls under 240px."""
    for words in ("first", "second"):
        r = client.post("/api/companies/AAPL/notes", json={"text": words}, headers=HEADER)
        assert r.status_code == 201, r.text
    read = client.get("/api/companies/AAPL/notes").json()["notes"]
    assert [n["text"] for n in read] == ["second", "first"]

    box = _drawn(_box())
    assert box["type"] == "div"
    assert box["props"]["className"] == "fb-menu fb-menu--filters app-notes-box"
    body = _one(box, "app-notes-box__body")
    assert body["props"]["className"] == "fb-menu__body app-notes-box__body"
    listed = _one(body, "app-notes-box__list")
    assert (listed["type"], listed["props"]["className"]) == ("ul", "app-list app-notes-box__list")
    items = [e for e in elements(listed) if e.get("type") == "li"]
    assert [item["props"]["key"] for item in items] == [7, 3]
    for item, note in zip(items, NOTES, strict=True):
        written, line = [kid for kid in item["props"]["children"] if kid is not None]
        assert written["type"] == "p"
        assert written["props"]["className"] == "body app-notes-box__text"
        assert text(written) == note["text"]
        assert line["props"]["className"] == "app-notes-box__chip"
        [chip] = _chips(line)
        assert chip["props"] == {
            "principal": note["principal"],
            "actor": note["actor"],
            "at": node("localIso", [note["at"]]),
            "children": [],
        }
    assert "max-height: 240px;" in _rule(".app-notes-box__body {")
    assert "white-space: pre-wrap;" in _rule(".app-notes-box__text {")


def test_the_box_without_a_note() -> None:
    """``No notes yet.`` where the read holds none; nothing in the list's place before the first
    read lands, which says neither that there are notes nor that there are none."""
    none = _one(_drawn(_box(notes=[])), "app-notes-box__none")
    assert (none["type"], text(none)) == ("p", "No notes yet.")
    assert classed(_drawn(_box(notes=[])), "app-notes-box__list") == []
    unread = _drawn(_box(notes=None, loading=True))
    assert _one(unread, "app-notes-box__body")["props"]["children"] == [None]
    assert "No notes yet." not in str(unread)


def test_the_box_while_its_notes_are_read() -> None:
    """While the notes are read, the box shows what it holds, faded, with no spinner; the field
    stays as it is."""
    tree = _drawn(_box(loading=True))
    body = _one(tree, "app-notes-box__body")
    assert body["props"]["className"] == "fb-menu__body app-notes-box__body is-loading"
    assert len(classed(body, "app-notes-box__text")) == 2
    assert _rule(".app-notes-box__body.is-loading {") == "opacity: 0.5;"
    assert "spinner" not in str(tree)


def test_a_failed_read_s_sentence() -> None:
    """One sentence in the list's place, which says to open Notes again; the field stays."""
    tree = _drawn(_box(notes=None, error="the server answered 500"))
    failed = _one(tree, "app-notes-box__failed")
    assert text(failed) == (
        "The notes did not load: the server answered 500. Open Notes again to retry."
    )
    assert classed(tree, "app-notes-box__list") == []
    assert classed(tree, "app-notes-box__field") != []


def test_the_box_s_field_and_button() -> None:
    """The field as Details had it, named for the company, its draft's text; then Add a note,
    disabled for an empty draft and while the note is posted."""
    tree = _drawn(_box())
    foot = _one(tree, "fb-menu__foot")
    form = _one(foot, "app-notes-box__new")
    assert form["type"] == "form"
    field = _one(form, "app-notes-box__field")
    assert field["type"] == "textarea"
    assert field["props"]["className"] == "control app-field app-notes-box__field"
    assert field["props"]["placeholder"] == field["props"]["aria-label"] == "A note on ACME"
    assert (field["props"]["rows"], field["props"]["value"]) == (3, "")
    [button] = _buttons(form, "Add a note")
    assert (button["props"]["type"], button["props"]["size"]) == ("submit", "sm")
    assert button["props"]["disabled"] is True
    for draft, disabled in (
        ({"text": "   "}, True),
        ({"text": "Margins look peaked."}, False),
        ({"text": "Margins look peaked.", "posting": True}, True),
    ):
        [button] = _buttons(_drawn(_box(draft=DRAFT | draft)), "Add a note")
        assert button["props"]["disabled"] is disabled, draft
    rule = _rule(".app-notes-box__field {")
    assert "width: 100%;" in rule and "resize: vertical;" in rule


def test_a_refusal_s_sentence_is_under_the_field() -> None:
    """The server's sentence as it arrives, under the field and its button, the text kept."""
    draft = DRAFT | {"text": "Margins look peaked.", "error": "a note needs text"}
    tree = _drawn(_box(draft=draft))
    foot = _one(tree, "fb-menu__foot")
    form, error = foot["props"]["children"]
    assert form["props"]["className"] == "app-notes-box__new"
    assert (error["type"], error["props"]["className"]) == ("p", "caption app-notes-box__error")
    assert text(error) == "a note needs text"
    assert _one(form, "app-notes-box__field")["props"]["value"] == "Margins look peaked."
    assert classed(_drawn(_box()), "app-notes-box__error") == []
    assert "color: var(--caution);" in _rule(".app-notes-box__error {")
    post = _function(_static_file("app.js"), "postNote")
    _in_order(
        post,
        "api.post('/api/companies/' + encodeURIComponent(symbol) + '/notes', { text: text })",
        "if (!r.ok) throw new Error(refusalDetail(r));",
        "draft.text = '';",
        ".catch(function (err) { draft.error = err.message; })",
    )


# ------------------------------------------------------------------------------- where it stands


def test_the_drawer_s_bar_holds_the_control_left_of_close() -> None:
    """Notes, for the drawer's company, then Close; the count the detail's while the drawer
    holds the company's detail, none while the drawer turns to the company or its read failed."""
    shown = {"symbol": answers.SYMBOL, "body": answers.DETAIL, "loading": False, "error": None}
    for drawer, words in (
        (shown, "Notes 2"),
        (shown | {"symbol": "ACME", "loading": True}, "Notes"),
        (shown | {"symbol": "ACME", "body": None, "error": "did not load"}, "Notes"),
    ):
        bar = _one(node("drawer", [drawer]), "app-drawer__bar")
        notes, close = bar["props"]["children"]
        assert notes["props"] == {
            "variant": "quiet",
            "size": "sm",
            "className": "app-notes-open",
            "children": [words],
        }
        assert close["props"] == {"variant": "quiet", "size": "sm", "children": ["Close"]}
    assert "notesControl(d.symbol, d.body && !d.loading ? d.body.noteCount : null," in (
        _function(_static_file("app.js"), "drawer")
    )
    assert _rule(".app-drawer__bar .app-notes-open {") == "margin-right: auto;"
    assert "justify-content: flex-end;" in _rule(".app-drawer__bar {")


def test_the_page_s_head_holds_it_before_the_watchlists_control() -> None:
    """In the head's controls, first: Notes with the detail's count, then Watchlists ▾ and
    Request research. A note taken reads the page again through its own read."""
    tree = node("companyPage.head", [answers.DETAIL, None], COMPANY)
    [actions] = classed(tree, "app-company__actions")
    notes, watch, request = actions["props"]["children"]
    assert notes == node("notesControl", [answers.SYMBOL, 2])
    assert notes["props"]["children"] == ["Notes 2"]
    assert watch["props"]["children"] == ["Watchlists ▾"]
    assert "app-request" in str(request)
    assert "P.notesControl(r.symbol, d.noteCount, load)," in _function(
        _static_file("company.js"), "head"
    )


# ------------------------------------------------------------------------------------- the shell


def test_the_box_opens_under_its_control_and_closes_as_the_popup_does() -> None:
    """A click on the control opens the box under it and reads the company's notes, or closes the
    box when it is the control's own; one box at a time, and never beside the watchlists popup.
    Escape, which hands focus back to the control, and a press or focus outside the box and its
    control close it; it follows its control as the page scrolls and closes when the control is
    gone."""
    script = _static_file("app.js")
    control = _function(script, "notesControl")
    assert "onClick: function (event) { openNotes(symbol, event.currentTarget, after); }" in (
        control
    )
    opened = _function(script, "openNotes")
    _in_order(
        opened,
        "if (state.notes && state.notes.anchor === anchor) {",
        "closeNotes();",
        "closeWatch();",
        "drafted(symbol);",
        "readNotes();",
    )
    assert "closeNotes();" in _function(script, "watch")
    read = _function(script, "readNotes")
    _in_order(
        read,
        "var request = ++latestNotes;",
        "getJson('/api/companies/' + encodeURIComponent(box.symbol) + '/notes')",
        "if (request !== latestNotes) return;",
        "box.notes = body.notes;",
        "box.error = err.message;",
    )
    assert "latestNotes++;" in _function(script, "closeNotes")
    for line in (
        "document.addEventListener('pointerdown', closeNotesOutside);",
        "document.addEventListener('focusin', closeNotesOutside);",
        (
            "document.addEventListener('scroll', function () { if (state.notes) renderNotes(); }, "
            "true);"
        ),
        "window.addEventListener('resize', function () { if (state.notes) renderNotes(); });",
    ):
        assert line in script, line
    escape = script.index("if (event.key !== 'Escape' || !state.notes) return;")
    _in_order(
        script[escape:],
        "var anchor = state.notes.anchor;",
        "closeNotes();",
        "if (anchor.isConnected) anchor.focus();",
    )
    # the drawer's own Escape waits while the box, a menu, is open
    assert "!document.querySelector('.fb-menu')) close();" in script
    shell = _function(script, "NotesBox")
    _in_order(
        shell,
        "if (!box.anchor.getClientRects().length) {",
        "closeNotes();",
        "place(ref.current, box.anchor);",
    )
    assert "place(ref.current, w.anchor);" in _function(script, "WatchMenu")
    assert "renderNotes();" in _function(script, "render")
    assert "position: fixed;" in _rule(".app-notes-box {")


def test_a_note_taken_reads_the_notes_and_the_company_again() -> None:
    """Taken, the field clears, the box still open on the company reads its notes again, so the
    new one is first, and the view the box opened from reads its company again, so the count
    follows: the drawer through reloadDetail, the company page through its own read. A control
    made without ``after`` reads nothing more, and a note it takes draws no error under the
    cleared field, since the post's catch would show the call's TypeError as a refusal."""
    script = _static_file("app.js")
    post = _function(script, "postNote")
    _in_order(
        post,
        "var box = state.notes;",
        "draft.text = '';",
        "if (state.notes && state.notes.symbol === symbol) readNotes();",
        "if (box.after) box.after();",
        ".catch(function (err) { draft.error = err.message; })",
    )
    assert post.count("box.after()") == 1
    assert script.count("function postNote(") == 1
    assert "notesControl(d.symbol, d.body && !d.loading ? d.body.noteCount : null,\n" in script
    assert "reread(d.symbol))" in _function(script, "drawer")
    assert "return function () { reloadDetail(symbol); };" in _function(script, "reread")


def test_the_draft_stays_until_another_company_shows() -> None:
    """The draft is the company's, kept when the box closes, until the drawer turns to another
    company or the company page shows one; the box opened on another company starts an empty
    one, and a box open on another company closes."""
    script = _static_file("app.js")
    drafted = _function(script, "drafted")
    assert "state.noteDraft = { symbol: symbol, text: '', error: null, posting: false };" in (
        drafted
    )
    shown = _function(script, "notesShown")
    assert "if (state.noteDraft && state.noteDraft.symbol !== symbol) state.noteDraft = null;" in (
        shown
    )
    assert "if (state.notes && state.notes.symbol !== symbol) closeNotes();" in shown
    _in_order(
        _function(script, "open"),
        "if (d && d.symbol === row.ticker && !d.error) return;",
        "if (!d || d.symbol !== row.ticker) notesShown(row.ticker);",
    )
    assert "notesShown" not in _function(script, "close")
    assert "notesShown" not in _function(script, "landed")
    # the page turns to another company as it is asked for one, never as it reads its own again,
    # and again as the read of another company lands or fails while the page shows, so a box
    # opened from the faded head of the company before it, while the read was out, closes as the
    # page turns; a landing after the reader left the view leaves the notes alone (run in node in
    # tests/web/test_company_load.py)
    load = _function(_static_file("company.js"), "load")
    shown = "if (state.symbol !== want.symbol) P.notesShown(want.symbol);"
    _in_order(load, "var want = P.company;", shown, "state.symbol = want.symbol;")
    landing = "if (state.symbol !== want.symbol && !mount.hidden) P.notesShown(want.symbol);"
    landed = load[load.index(".then(function (found) {") : load.index(".catch(function (err) {")]
    failed = load[load.index(".catch(function (err) {") :]
    for branch in (landed, failed):
        _in_order(branch, "if (request !== latest) return;", landing, "state.symbol = want.symbol;")
    assert load.count(shown) == 1 and load.count(landing) == 2
    assert load.count("P.notesShown(") == 3


def test_the_box_s_classes_are_its_own() -> None:
    """Every class of the control and the box that is not the bundle's, a type style's or a
    shared one is new: no element the app drew before the control carries it, so the box's rules
    reach the box alone. Each is named in the scripts only where the control and the box are
    built, and in no part of the bundle."""
    trees = [
        node("notesControl", ["ACME", 3]),
        _drawn(_box(draft=DRAFT | {"error": "a note needs text"})),
        _drawn(_box(notes=[])),
        _drawn(_box(notes=None, error="the server answered 500")),
    ]
    names = {
        name
        for tree in trees
        for e in elements(tree)
        for name in str(e["props"].get("className") or "").split()
    }
    own = {name for name in names if name.startswith("app-notes")}
    assert own == {
        "app-notes-open",
        "app-notes-box",
        "app-notes-box__body",
        "app-notes-box__list",
        "app-notes-box__text",
        "app-notes-box__chip",
        "app-notes-box__none",
        "app-notes-box__failed",
        "app-notes-box__new",
        "app-notes-box__field",
        "app-notes-box__error",
    }
    shared = names - own
    assert shared <= {
        "fb-menu",
        "fb-menu--filters",
        "fb-menu__body",
        "fb-menu__foot",
        "app-list",
        "app-muted",
        "app-field",
        "body",
        "caption",
        "control",
    }
    app = _static_file("app.js")
    built = _function(app, "notesControl") + _function(app, "notesBox")
    scripts: list[Path] = sorted(STATIC.glob("*.js")) + [
        STATIC / "design-system" / "components" / "bundle.js"
    ]
    for name in own:
        token = re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])")
        for script in scripts:
            found = len(token.findall(script.read_text(encoding="utf-8")))
            expected = len(token.findall(built)) if script.name == "app.js" else 0
            assert found == expected, (name, script.name)
        assert token.findall(built), name
    assert "app-notes__" not in _static_file("index.html")
