"""The drawer's flag list (spec 2026-11-13 8a): where the company's detail carries a review with a
value, the review that fills the screen's row, the list is the review's flags under a line that
says so, as the row's Flags and Warnings read them; else the snapshot's. The page's own script runs
in node after the bundle (``page.mjs``), and the test reads what ``drawerFlags`` returns."""

import json
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("page.mjs")
STATIC = Path(str(resources.files("fairband.web").joinpath("static")))
BUNDLE = STATIC / "design-system" / "components" / "bundle.js"
APP = STATIC / "app.js"

SNAPSHOT = [
    {"code": "share-count-gap", "word": "Share count and market cap disagree", "sentence": "s"}
]
REVIEW = [{"code": "thin-ntm", "word": "Thin NTM consensus", "sentence": "t"}]


def _call(helper: str, *args: Any) -> Any:
    """What app.js's ``helper`` returns on ``args``, through JSON."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(HARNESS), str(BUNDLE), str(APP), helper],
        input=json.dumps(list(args)),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


def _function(source: str, name: str) -> str:
    """The text of the top-level function ``name`` in ``source``, to the next one."""
    start = source.index(f"\n  function {name}(")
    end = source.index("\n  function ", start + 1)
    return source[start:end]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_drawer_reads_the_review_s_flags() -> None:
    """Spec 2026-11-13 8a: a review with a value gives the drawer its flags; a refused review,
    a review without flags and no review leave the snapshot's."""
    body = {"result": {"flags": SNAPSHOT}, "review": {"value": 11.0, "flags": REVIEW}}
    assert _call("drawerFlags", body) == {"flags": REVIEW, "reviewed": True}
    settled = {"result": {"flags": SNAPSHOT}, "review": {"value": 11.0, "flags": []}}
    assert _call("drawerFlags", settled) == {"flags": [], "reviewed": True}
    for review in (None, {"value": None, "flags": None}, {"value": 11.0}):
        body = {"result": {"flags": SNAPSHOT}, "review": review}
        assert _call("drawerFlags", body) == {"flags": SNAPSHOT, "reviewed": False}


def test_details_lists_them_under_its_flags_heading() -> None:
    """Details draws the list ``drawerFlags`` gives under the heading "Flags", with the line
    "The review's flags." above it where they are the review's; the inputs and the intermediates
    beside it stay the snapshot's."""
    details = _function(APP.read_text(encoding="utf-8"), "details")
    assert "var flagged = drawerFlags(body);" in details
    flags = details[details.index("section('flags', 'Flags',") :]
    assert flags.index("flagged.reviewed\n") < flags.index("'The review\\'s flags.'")
    assert flags.index("'The review\\'s flags.'") < flags.index("flagged.flags.map(")
    assert "r.flags" not in details
    assert "inputsTable(r.inputs)" in details and "intermediates(r.intermediates)" in details
