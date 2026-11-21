"""The moat class on the company page and in the drawer (spec 2026-11-19 8.8, 9): the stamp after
the phase badge, ``WIDE MOAT``, ``NARROW MOAT``, ``NO MOAT``, or ``MOAT NOT SET`` with a dashed
border for a company with no row in the moat table; after it a compact principal chip where the
class is the owner's or an agent's, its hover the day and the reason; then, on the company page
alone, a quiet small button, ``Change ▾``, or ``Set ▾`` with no row, which opens a box built as the
Notes box is: the line that says whose the class is, the reason under it, the three classes with
the one in force pressed, the field ``Reason (optional)``, ``Set moat class``, and on the owner's
or an agent's row of a company the file holds, ``Use Fairband's class (Narrow)``. A write reads
the company again; a refusal's sentence stands under the buttons.

The page's own scripts run in node after the bundle (``support.page``), and the tests read the
trees ``moatStamp``, ``moatChip``, ``moatControl``, ``moatBox``, the drawer's ``sections`` and the
company page's ``head`` return; ``moat.mjs`` drives the box's writes with a fetch of its own; the
listeners around the box are read as text."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support import page_answers as answers
from support.page import BUNDLE, NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

COMPANY = STATIC / "company.js"
DRIVER = Path(__file__).parent / "moat.mjs"
SYMBOL = "BF.B"
REASON = "Its brands keep rivals out."

# The three rows a company may have: the file's, Narrow; the owner's Wide over it, with a reason;
# an agent's Wide over it, with its reason.
FILE: dict[str, Any] = answers.MOAT_FILE | {"class": "Narrow", "fileClass": "Narrow"}
OWNER: dict[str, Any] = FILE | {
    "class": "Wide",
    "source": "owner",
    "fileVersion": None,
    "previous": "Narrow",
    "reason": REASON,
}
AGENT: dict[str, Any] = OWNER | {
    "source": "agent",
    "actor": "claude-opus-5-5",
    "reason": "Its bottlers' network keeps rivals out.",
}


def _detail(row: dict[str, Any] | None) -> dict[str, Any]:
    """BF.B's detail with ``row`` its row of the moat table, ``None`` for none."""
    found = answers.detail(moat=None if row is None else row["class"], moatClass=row)
    found["result"]["symbol"] = SYMBOL
    return found


def _box(row: dict[str, Any] | None, **changes: Any) -> dict[str, Any]:
    """The box open on BF.B with ``row``, the class in force pressed, nothing typed."""
    box: dict[str, Any] = {
        "symbol": SYMBOL,
        "row": row,
        "pick": None if row is None else row["class"],
        "draft": "",
        "error": None,
        "posting": False,
    }
    return box | changes


def _drawn(box: dict[str, Any]) -> Any:
    return node("moatBox", [box])


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


def _drive(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The trace of ``moat.mjs`` on ``steps``, one entry a step."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(DRIVER), str(BUNDLE), str(STATIC / "app.js")],
        input=json.dumps(steps),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    trace: list[dict[str, Any]] = json.loads(done.stdout)
    return trace


# ------------------------------------------------------------------------------------ the stamp


def test_the_stamp_s_four_words() -> None:
    """An outlined label in the Words table's words; ``MOAT NOT SET``, dashed, with no row."""
    for moat, words in (("Wide", "WIDE MOAT"), ("Narrow", "NARROW MOAT"), ("None", "NO MOAT")):
        stamp = node("moatStamp", [{"moat": moat}])
        assert stamp["type"] == "span"
        assert stamp["props"]["className"] == "label app-moat"
        assert text(stamp) == words
    unset = node("moatStamp", [{"moat": None}])
    assert unset["type"] == "span"
    assert unset["props"]["className"] == "label app-moat app-moat--unset"
    assert text(unset) == "MOAT NOT SET"


def test_the_unset_stamp_is_dashed() -> None:
    """The stamp's own outline, dashed; nothing else of it changes."""
    assert _rule(".app-moat--unset {") == "border-style: dashed;"


# ------------------------------------------------------------------------------------- the chip


def test_the_chip_by_whose_class_it_is() -> None:
    """The owner's or an agent's class has a compact principal chip, the agent's with its model,
    its hover the day and the reason, or the day alone; the file's class has none, and so does a
    company with no row: quiet is the signal that nothing was changed."""
    owner = node("moatChip", [{"moatClass": OWNER}])
    assert owner["props"] == {
        "principal": "owner",
        "actor": None,
        "compact": True,
        "reason": "19 Nov 2026: Its brands keep rivals out.",
        "children": [],
    }
    agent = node("moatChip", [{"moatClass": AGENT}])
    assert agent["props"] == {
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "compact": True,
        "reason": "19 Nov 2026: Its bottlers' network keeps rivals out.",
        "children": [],
    }
    bare = node("moatChip", [{"moatClass": OWNER | {"reason": None}}])
    assert bare["props"]["reason"] == "19 Nov 2026"
    assert node("moatChip", [{"moatClass": FILE}]) is None
    assert node("moatChip", [{"moatClass": None}]) is None
    # the bundle's title writes the reason after its principal's note
    title = node("Fairband.PrincipalChip", [owner["props"]])["props"]["title"]
    assert title == "Written by you — 19 Nov 2026: Its brands keep rivals out."


# ---------------------------------------------------------------------------------- the control


def test_the_control_s_words() -> None:
    """A quiet small button: ``Change ▾`` on a company with a row, the file's, the owner's or an
    agent's; ``Set ▾`` on one with none."""
    for row, words in (
        (FILE, "Change ▾"),
        (OWNER, "Change ▾"),
        (AGENT, "Change ▾"),
        (None, "Set ▾"),
    ):
        control = node("moatControl", [_detail(row)])
        assert control["props"] == {
            "variant": "quiet",
            "size": "sm",
            "className": "app-moat-open",
            "children": [words],
        }


# -------------------------------------------------------------------------------------- the box


def test_a_long_reason_keeps_the_box_whole() -> None:
    """Look D1: inside the bundle's menu body, which scrolls at 368px, no part of the box's column
    shrinks, so the classes and the field keep their height under a reason of 900 characters; the
    reason scrolls in an area of its own, six lines of body text; and the focus on open does not
    scroll the box, so the line that says whose the class is stays in view."""
    assert _rule(".app-moat-box__body > * {") == "flex: none;"
    assert _rule(".app-moat-box__reason {") == (
        "margin: 0; max-height: 120px; overflow-y: auto; white-space: pre-wrap; "
        "overflow-wrap: anywhere;"
    )
    opened = " ".join(_function(_static_file("app.js"), "MoatBox").split())
    assert (
        "(menu.querySelector('[aria-pressed=\"true\"]') || menu.querySelector('button'))"
        " .focus({ preventScroll: true });"
    ) in opened


def test_the_box_s_four_states() -> None:
    """Built as the Notes box is. The line that says whose the class is: the file's, with the
    table's version and its day; the owner's, since its day, and the class before it; an agent's,
    its chip, then the same; none with no row. The reason under it where one is on file. The three
    classes, the one in force pressed, none with no row. The return to the file's class only on
    the owner's or an agent's row of a company the file holds."""
    lines = {
        "file": "Fairband's class, table version 1, judged 19 Nov 2026.",
        "owner": "Your class since 19 Nov 2026. Before: Narrow.",
        "agent": " since 19 Nov 2026. Before: Narrow.",
    }
    for state, row, reason, back in (
        ("file", FILE, None, None),
        ("owner", OWNER, REASON, "Use Fairband's class (Narrow)"),
        ("agent", AGENT, AGENT["reason"], "Use Fairband's class (Narrow)"),
        ("none", None, None, None),
    ):
        tree = _drawn(_box(row))
        assert tree["type"] == "div"
        assert tree["props"]["className"] == "fb-menu fb-menu--filters app-moat-box"
        assert (tree["props"]["role"], tree["props"]["aria-label"]) == ("group", "Moat class")
        body = _one(tree, "fb-menu__body")
        assert body["props"]["className"] == "fb-menu__body app-moat-box__body"
        whose = classed(tree, "app-moat-box__whose")
        if row is None:
            assert whose == []
        else:
            [line] = whose
            assert (line["type"], line["props"]["className"]) == (
                "p",
                "caption app-moat-box__whose",
            )
            assert text(line) == lines[state], state
            [day] = [e for e in elements(line) if e.get("type") == "time"]
            assert day["props"]["dateTime"] == "2026-11-19"
        chips = _chips(_one(tree, "app-moat-box__whose")) if row is not None else []
        if state == "agent":
            assert [c["props"] for c in chips] == [
                node("moatChip", [{"moatClass": AGENT}])["props"]
            ]
            assert whose[0]["props"]["children"][0] == node("moatChip", [{"moatClass": AGENT}])
        else:
            assert chips == []
        said = classed(tree, "app-moat-box__reason")
        if reason is None:
            assert said == []
        else:
            [p] = said
            assert (p["type"], p["props"]["className"]) == ("p", "body app-moat-box__reason")
            assert text(p) == reason
        seg = _one(tree, "app-fin__seg")
        assert seg["props"]["className"] == "app-fin__seg app-moat-box__classes"
        assert (seg["props"]["role"], seg["props"]["aria-label"]) == ("group", "Moat class")
        classes = [e for e in elements(seg) if e.get("type") == "button"]
        assert [text(b) for b in classes] == ["None", "Narrow", "Wide"]
        for b in classes:
            assert b["props"]["type"] == "button"
            assert b["props"]["className"] == "control"
        pressed = [text(b) for b in classes if b["props"]["aria-pressed"] == "true"]
        assert pressed == ([] if row is None else [row["class"]]), state
        assert {b["props"]["aria-pressed"] for b in classes} <= {"true", "false"}
        field = _one(tree, "app-moat-box__field")
        assert field["type"] == "textarea"
        assert field["props"]["className"] == "control app-field app-moat-box__field"
        assert field["props"]["placeholder"] == "Reason (optional)"
        assert field["props"]["aria-label"] == "Reason"
        assert (field["props"]["rows"], field["props"]["value"]) == (2, "")
        foot = _one(tree, "fb-menu__foot")
        [set_] = _buttons(foot, "Set moat class")
        assert set_["props"]["size"] == "sm" and "variant" not in set_["props"]
        assert set_["props"]["disabled"] is (row is None)
        returns = [e for e in elements(foot) if text(e).startswith("Use ")]
        if back is None:
            assert returns == [], state
        else:
            [ret] = returns
            assert ret["props"]["children"] == [back]
            assert (ret["props"]["variant"], ret["props"]["size"]) == ("quiet", "sm")
            assert ret["props"]["disabled"] is False
    # no Before: without a class before it
    first = _drawn(_box(OWNER | {"previous": None}))
    assert text(_one(first, "app-moat-box__whose")) == "Your class since 19 Nov 2026."
    # "Before: Narrow." stays whole on the line: a span that does not wrap (look D3)
    for row in (OWNER, AGENT):
        [before] = classed(_drawn(_box(row)), "app-moat-box__before")
        assert (before["type"], text(before)) == ("span", "Before: Narrow."), row["source"]
    for row in (FILE, OWNER | {"previous": None}, AGENT | {"previous": None}):
        assert classed(_drawn(_box(row)), "app-moat-box__before") == [], row["source"]
    assert _rule(".app-moat-box__before {") == "white-space: nowrap;"
    # the owner's row of a company the file does not hold: no return
    entrant = _drawn(_box(OWNER | {"previous": None, "fileClass": None}))
    assert [e for e in elements(entrant) if "Use Fairband" in text(e)] == []
    # a class picked, a reason typed, then the write out: the buttons wait
    picked = _drawn(_box(None, pick="Wide", draft="A brand."))
    assert [text(b) for b in elements(picked) if b["props"].get("aria-pressed") == "true"] == [
        "Wide"
    ]
    assert _one(picked, "app-moat-box__field")["props"]["value"] == "A brand."
    [set_] = _buttons(picked, "Set moat class")
    assert set_["props"]["disabled"] is False
    posting = _drawn(_box(OWNER, posting=True))
    [set_] = _buttons(posting, "Set moat class")
    [ret] = _buttons(posting, "Use Fairband's class (Narrow)")
    assert set_["props"]["disabled"] is True and ret["props"]["disabled"] is True


def test_the_box_s_classes_are_its_own() -> None:
    """Every class of the control and the box that is not the bundle's, a type style's or a
    shared one starts ``app-moat``, and is named in the scripts only where the stamp, the control
    and the box are built, and in no part of the bundle."""
    trees = [
        node("moatStamp", [{"moat": None}]),
        node("moatControl", [_detail(FILE)]),
        _drawn(_box(OWNER, error="a refresh is running: set the class when it ends")),
        _drawn(_box(AGENT)),
    ]
    names = {
        name
        for tree in trees
        for e in elements(tree)
        for name in str(e["props"].get("className") or "").split()
    }
    own = {name for name in names if name.startswith("app-moat")}
    assert own == {
        "app-moat",
        "app-moat--unset",
        "app-moat-open",
        "app-moat-box",
        "app-moat-box__body",
        "app-moat-box__whose",
        "app-moat-box__before",
        "app-moat-box__reason",
        "app-moat-box__classes",
        "app-moat-box__field",
        "app-moat-box__buttons",
        "app-moat-box__error",
    }
    assert names - own <= {
        "fb-menu",
        "fb-menu--filters",
        "fb-menu__body",
        "fb-menu__foot",
        "app-fin__seg",
        "app-field",
        "body",
        "caption",
        "control",
        "label",
    }
    app = _static_file("app.js")
    built = "".join(
        _function(app, name)
        for name in ("moatStamp", "moatControl", "MoatBox", "moatBox", "moatLine")
    )
    for name in own - {"app-moat"}:
        token = re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])")
        for script in sorted(STATIC.glob("*.js")) + [BUNDLE]:
            found = len(token.findall(script.read_text(encoding="utf-8")))
            expected = len(token.findall(built)) if script.name == "app.js" else 0
            assert found == expected, (name, script.name)


# ------------------------------------------------------------------------------------ the writes


def test_the_set_and_the_return() -> None:
    """A set is a PUT of the class picked to the company's own address, the dot of its symbol
    kept, with the reason typed and none where it is blank; a return is a DELETE. While the write
    is out the buttons wait; taken, the box closes, focus goes back to the control, the screen's
    rows load again, since the company was valued again, and the page reads the company again."""
    trace = _drive(
        [
            {"do": "open", "detail": _detail(FILE)},
            {"do": "pick", "class": "Wide"},
            {"do": "type", "text": "   "},
            {"do": "set"},
            {"do": "answer", "status": 200, "body": {"moatClass": OWNER, "snapshot": {}}},
            {"do": "open", "detail": _detail(OWNER)},
            {"do": "type", "text": f"  {REASON} "},
            {"do": "set"},
            {"do": "answer", "status": 200, "body": {"moatClass": OWNER, "snapshot": {}}},
            {"do": "open", "detail": _detail(OWNER)},
            {"do": "return"},
            {"do": "answer", "status": 200, "body": {"moatClass": FILE, "snapshot": {}}},
        ]
    )
    opened, picked, typed, sent, taken = trace[:5]
    assert opened["box"] == {
        "whose": "Fairband's class, table version 1, judged 19 Nov 2026.",
        "reason": None,
        "pressed": ["Narrow"],
        "draft": "",
        "set": False,
        "back": None,
        "error": None,
    }
    assert opened["fetched"] == []
    assert picked["box"]["pressed"] == ["Wide"]
    assert typed["box"]["draft"] == "   "
    assert sent["fetched"] == [["PUT", "/api/companies/BF.B/moat", {"class": "Wide"}]]
    assert sent["box"]["set"] is True  # the write is out
    assert (taken["box"], taken["afters"], taken["focused"]) == (None, 1, 1)
    assert [f[:2] for f in taken["fetched"]] == [["GET", "/api/screen?sort=ticker&dir=asc"]]
    reopened, _, with_reason, taken = trace[5:9]
    assert reopened["box"]["whose"] == "Your class since 19 Nov 2026. Before: Narrow."
    assert reopened["box"]["reason"] == REASON
    assert reopened["box"]["back"] == ["Use Fairband's class (Narrow)", False]
    assert with_reason["fetched"] == [
        ["PUT", "/api/companies/BF.B/moat", {"class": "Wide", "reason": REASON}]
    ]
    assert (taken["box"], taken["afters"]) == (None, 2)
    _, returned, taken = trace[9:]
    assert returned["fetched"] == [["DELETE", "/api/companies/BF.B/moat", {}]]
    assert returned["box"]["back"] == ["Use Fairband's class (Narrow)", True]
    assert (taken["box"], taken["afters"], taken["focused"]) == (None, 3, 3)
    # the address is built as the page's other addresses of a company are
    write = _function(_static_file("app.js"), "moatPath")
    assert "'/api/companies/' + encodeURIComponent(symbol) + '/moat'" in write


def test_a_write_reads_the_drawer_s_company_again() -> None:
    """The drawer outlives the turn to the company page: where it shows the company, a taken set
    and a taken return read its detail again, so beside the screen's reloaded row it draws the new
    stamp and chip; a refusal reads nothing, and a drawer that shows another company is left as it
    is."""
    detail = f"/api/companies/{SYMBOL}"
    owner = _detail(OWNER)
    other = answers.detail()  # LFOX, the file's Wide
    trace = _drive(
        [
            {"do": "drawer", "symbol": SYMBOL},
            {"do": "read", "url": detail, "body": _detail(FILE)},
            {"do": "open", "detail": _detail(FILE)},
            {"do": "pick", "class": "Wide"},
            {"do": "set"},
            {"do": "answer", "status": 409, "body": {"detail": "a refresh is running"}},
            {"do": "set"},
            {"do": "answer", "status": 200, "body": {"moatClass": OWNER, "snapshot": {}}},
            {"do": "read", "url": detail, "body": owner},
            {"do": "open", "detail": owner},
            {"do": "return"},
            {"do": "answer", "status": 200, "body": {"moatClass": FILE, "snapshot": {}}},
            {"do": "drawer", "symbol": answers.SYMBOL},
            {"do": "read", "url": f"/api/companies/{answers.SYMBOL}", "body": other},
            {"do": "open", "detail": owner},
            {"do": "set"},
            {"do": "answer", "status": 200, "body": {"moatClass": OWNER, "snapshot": {}}},
        ]
    )
    opened, shown = trace[:2]
    assert [f[:2] for f in opened["fetched"]] == [["GET", detail]]
    assert shown["drawer"] == {
        "symbol": SYMBOL,
        "loading": False,
        "stamp": "NARROW MOAT",
        "chip": None,
    }
    refused = trace[5]
    assert refused["box"]["error"] == "a refresh is running"
    assert (refused["fetched"], refused["afters"]) == ([], 0)
    taken, landed = trace[7:9]
    assert [f[:2] for f in taken["fetched"]] == [
        ["GET", "/api/screen?sort=ticker&dir=asc"],
        ["GET", detail],
    ]
    assert taken["afters"] == 1
    assert landed["drawer"] == {
        "symbol": SYMBOL,
        "loading": False,
        "stamp": "WIDE MOAT",
        "chip": "owner",
    }
    returned = trace[11]
    assert [f[:2] for f in returned["fetched"]] == [
        ["GET", "/api/screen?sort=ticker&dir=asc"],
        ["GET", detail],
    ]
    # the drawer turned to another company: a write on BF.B leaves it
    elsewhere = trace[16]
    assert elsewhere["drawer"]["symbol"] == answers.SYMBOL
    assert [f[:2] for f in elsewhere["fetched"]] == [["GET", "/api/screen?sort=ticker&dir=asc"]]
    assert elsewhere["afters"] == 3


def test_a_refusal_s_sentence_under_the_buttons() -> None:
    """The server's sentence as it arrives, under the buttons, the box open and what was picked
    and typed kept; the status where the server sent no sentence. The company is not read again.
    A box drawn with a refusal holds it in the foot after the buttons, in caution."""
    refusal = "a refresh is running: set the class when it ends"
    trace = _drive(
        [
            {"do": "open", "detail": _detail(None)},
            {"do": "pick", "class": "Wide"},
            {"do": "type", "text": REASON},
            {"do": "set"},
            {"do": "answer", "status": 409, "body": {"detail": refusal}},
            {"do": "set"},
            {"do": "answer", "status": 500, "body": "Internal Server Error"},
        ]
    )
    opened = trace[0]["box"]
    assert opened["whose"] is None and opened["pressed"] == [] and opened["set"] is True
    refused = trace[4]
    assert refused["box"] == {
        "whose": None,
        "reason": None,
        "pressed": ["Wide"],
        "draft": REASON,
        "set": False,
        "back": None,
        "error": refusal,
    }
    assert (refused["afters"], refused["fetched"]) == (0, [])
    assert trace[5]["box"]["error"] is None  # a new write clears it
    assert trace[6]["box"]["error"] == "the server answered 500"
    tree = _drawn(_box(OWNER, error=refusal))
    foot = _one(tree, "fb-menu__foot")
    buttons, error = foot["props"]["children"]
    assert buttons["props"]["className"] == "app-moat-box__buttons"
    assert (error["type"], error["props"]["className"]) == ("p", "caption app-moat-box__error")
    assert error["props"]["role"] == "alert"  # said, since the focus does not pass it
    assert text(error) == refusal
    # the disabled Set dropped the focus while the write was out: a refusal hands it back to Set,
    # a second refusal too, without scrolling the box (look D2); the driver runs no effect, so the
    # effect is read as text
    _in_order(
        _function(_static_file("app.js"), "MoatBox"),
        "React.useEffect(function () {",
        "if (box.posting || !box.error) return;",
        "var set = ref.current.querySelector('.app-moat-box__buttons button');",
        "if (set) set.focus({ preventScroll: true });",
        "}, [box.posting, box.error]);",
    )
    assert classed(_drawn(_box(OWNER)), "app-moat-box__error") == []
    assert "color: var(--caution);" in _rule(".app-moat-box__error {")


def test_one_box_at_a_time() -> None:
    """The moat box closes Notes and the watchlists popup as it opens, and Notes closes it; a
    press on its own control closes it. A press or focus outside it and its control, and Escape,
    which hands focus back to the control, close it; it follows its control as the page scrolls
    and closes when the control is gone or the page turns to another company."""
    trace = _drive(
        [
            {"do": "open", "detail": _detail(FILE)},
            {"do": "notes"},
            {"do": "open", "detail": _detail(FILE)},
            {"do": "open", "detail": _detail(FILE)},
        ]
    )
    assert [(step["box"] is not None, step["notes"]) for step in trace] == [
        (True, False),
        (False, True),
        (True, False),
        (False, False),
    ]
    script = _static_file("app.js")
    _in_order(
        _function(script, "openMoat"),
        "if (state.moat && state.moat.anchor === anchor) {",
        "closeMoat();",
        "closeWatch();",
        "closeNotes();",
        "renderMoat();",
    )
    assert "closeMoat();" in _function(script, "openNotes")
    assert "closeMoat();" in _function(script, "watch")
    assert "if (state.moat) closeMoat();" in _function(script, "closePopups")
    assert "if (state.moat && state.moat.symbol !== symbol) closeMoat();" in _function(
        script, "notesShown"
    )
    for line in (
        "document.addEventListener('pointerdown', closeMoatOutside);",
        "document.addEventListener('focusin', closeMoatOutside);",
        (
            "document.addEventListener('scroll', function () { if (state.moat) renderMoat(); }, "
            "true);"
        ),
        "window.addEventListener('resize', function () { if (state.moat) renderMoat(); });",
    ):
        assert line in script, line
    _in_order(
        _function(script, "closeMoatOutside"),
        "if (moatMount.contains(event.target) || box.anchor.contains(event.target)) return;",
        "closeMoat();",
    )
    escape = script.index("if (event.key !== 'Escape' || !state.moat) return;")
    _in_order(
        script[escape:],
        "var anchor = state.moat.anchor;",
        "closeMoat();",
        "if (anchor.isConnected) anchor.focus();",
    )
    _in_order(
        _function(script, "MoatBox"),
        "if (!box.anchor.getClientRects().length) {",
        "closeMoat();",
        "place(ref.current, box.anchor);",
    )
    assert "renderMoat();" in _function(script, "render")
    assert "position: fixed;" in _rule(".app-moat-box {")


# --------------------------------------------------------------------------------- where it shows


def test_the_page_s_head_and_the_drawer_s() -> None:
    """On the company page's line, after the phase badge: the stamp, the chip where the class is
    the owner's or an agent's, then the control, which reads the page again after a write. In the
    drawer's head: the stamp and the chip, and no control."""
    for row in (FILE, OWNER, AGENT, None):
        detail = _detail(row)
        head = node("companyPage.head", [detail, None], COMPANY)
        [line] = classed(head, "app-company__line")
        kids = [kid for kid in line["props"]["children"] if kid is not None]
        badge = next(i for i, kid in enumerate(kids) if "phase" in kid["props"])
        stamp, *rest = kids[badge + 1 :]
        assert stamp == node("moatStamp", [detail])
        chip = node("moatChip", [detail])
        assert rest == ([chip] if chip else []) + [node("moatControl", [detail])], row
        drawer = node("sections", [detail])
        [top] = classed(drawer, "app-drawer__head")
        kids = [kid for kid in top["props"]["children"] if kid is not None]
        badge = next(i for i, kid in enumerate(kids) if "phase" in kid["props"])
        assert kids[badge + 1] == node("moatStamp", [detail])
        if chip:
            assert kids[badge + 2] == chip
        assert classed(drawer, "app-moat-open") == []
    assert "P.moatStamp(d), P.moatChip(d), P.moatControl(d, load))," in _function(
        _static_file("company.js"), "head"
    )
    assert classed(node("companyPage.head", [answers.unset_detail(), None], COMPANY), "app-moat")
