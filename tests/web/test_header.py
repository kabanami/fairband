"""The header and the status line under it across the views (the company page's design, the
founder's rulings of 2026-11-17). The line of the last refresh and its Details describe the whole
universe, so the Screen and the other views of many companies keep them; the company page, a page
of one company, draws neither: the header's stamp already says when the engine ran. A refresh
that runs still draws its bar there, and a notice its sentence, since the header has neither.
The header's finder stands in its right slot on every view but the Screen, whose table has a
field of its own. The bundle, app.js, finder.js and controls.js run in node
(``tests/web/header.mjs``) on steps the test gives, and the tests read the trace."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support.page import BUNDLE, NODE, STATIC
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

DRIVER = Path(__file__).parent / "header.mjs"
CURRENT = "/api/refresh/current"
LAST: dict[str, Any] = {
    "refresh": None,
    "last": {
        "id": 66,
        "kind": "full",
        "status": "done",
        "stage": "done",
        "startedAt": "2026-11-17T04:07:47+00:00",
        "finishedAt": "2026-11-17T04:26:16+00:00",
        "message": None,
        "calibration": {
            "flagged": 625,
            "flags": {"few-analysts": 659},
            "phases": {"Mature Growth": 787, "Mature Stable": 478, "unclassified": 14},
            "refused": {"data fetch failed: income-annual": 1, "no positive trailing earnings": 27},
            "total": 1569,
            "valued": 1371,
        },
    },
    "error": None,
}
LAST["shown"] = LAST["last"]  # the run the line describes: the last one, but after a moat write
RUNNING: dict[str, Any] = {
    "refresh": {
        "id": 67,
        "kind": "full",
        "stage": "fetch",
        "done": 40,
        "failed": 0,
        "remaining": 1529,
        "current": "AAPL",
    }
}
LANDED = {"do": "answer", "url": CURRENT, "status": 200, "body": LAST}
LINE_END = " · 1,371 of 1,569 valued · 1 failed"


def _trace(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(DRIVER), str(BUNDLE)]
        + [str(STATIC / name) for name in ("app.js", "finder.js", "controls.js")],
        input=json.dumps(steps),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return list(json.loads(done.stdout))


def _show(view: str, section: str | None = None) -> dict[str, Any]:
    return {"do": "show", "view": view, "section": section}


def test_the_screen_keeps_the_last_refreshs_line_its_details_and_no_finder() -> None:
    [landed] = _trace([LANDED])
    assert landed["view"] == "screen"
    assert landed["status"].startswith("full done ") and landed["status"].endswith(LINE_END)
    assert landed["details"] is True and landed["run"] is False and landed["notice"] is None
    assert landed["finder"] is False
    assert landed["actions"] == ["Refresh prices", "Refresh all"]


def test_a_page_of_one_company_draws_no_last_line_and_no_details() -> None:
    """The status region stays, empty, so a run that starts is announced from a region the page
    already had; the header marks no view; back on the Screen the line and Details return."""
    _, page, screen = _trace([LANDED, _show("company", "AAPL"), _show("screen")])
    assert page["view"] == ""
    assert page["status"] == "" and page["details"] is False
    assert page["run"] is False and page["notice"] is None
    assert page["bar"] == "app-bar app-bar--bare"  # a bar that draws nothing takes no room
    assert page["finder"] is True
    assert screen["status"].endswith(LINE_END) and screen["details"] is True
    assert screen["bar"] == "app-bar"
    assert screen["finder"] is False


@pytest.mark.parametrize("view", ["groups", "watchlists", "methodology", "settings", "inbox"])
def test_a_view_of_many_companies_keeps_the_line_and_has_the_finder(view: str) -> None:
    _, shown = _trace([LANDED, _show(view)])
    assert shown["view"] == view
    assert shown["status"].endswith(LINE_END) and shown["details"] is True
    assert shown["finder"] is True


def test_a_running_refresh_draws_its_bar_on_a_page_of_one_company() -> None:
    """The header has no bar of its own, so the run's progress and its Cancel stay where they
    are on every view."""
    _, page = _trace(
        [{"do": "answer", "url": CURRENT, "status": 200, "body": RUNNING}, _show("company", "AAPL")]
    )
    assert page["run"] is True and page["details"] is False and page["bar"] == "app-bar"
    assert page["actions"] == ["Cancel"]
    assert page["finder"] is True


def test_a_notice_still_draws_on_the_company_page_and_before_any_refresh_the_line_is_empty() -> (
    None
):
    """The refresh's state fails to load while the company page shows: its sentence is drawn
    under the header. No refresh is known, and the Screen's ``No refresh has run yet.`` is not
    this page's to say."""
    page, failed, screen = _trace(
        [
            _show("company", "AAPL"),
            {
                "do": "answer",
                "url": CURRENT,
                "status": 500,
                "body": {"detail": "the store is locked"},
            },
            _show("screen"),
        ]
    )
    assert page["status"] == "" and page["notice"] is None
    assert failed["status"] == "" and failed["bar"] == "app-bar"
    assert failed["notice"].startswith("The refresh status did not load: ")
    assert screen["status"] == "No refresh has run yet." and screen["notice"] == failed["notice"]


def _ended(status: str, message: str) -> dict[str, Any]:
    """The refresh's state after a run that did not end done: its message and no calibration."""
    last = LAST["last"] | {"status": status, "message": message, "calibration": None}
    body = {"refresh": None, "last": last, "shown": last, "error": None}
    return {"do": "answer", "url": CURRENT, "status": 200, "body": body}


@pytest.mark.parametrize(
    ("status", "message"),
    [("failed", "no company was admitted"), ("cancelled", "cancelled after 40 companies")],
)
def test_a_run_that_did_not_end_done_says_so_on_a_page_of_one_company(
    status: str, message: str
) -> None:
    """The header's stamp is the latest run's finish whatever its status, and the line under the
    header is what says how the run ended. Without the line a failed or cancelled run would read
    there as a fresh one, over figures it did not renew: such a run keeps its line on the company
    page, with no Details."""
    _, page = _trace([_ended(status, message), _show("company", "AAPL")])
    assert page["status"].startswith(f"full {status} ")
    assert page["status"].endswith(" · " + message)
    assert page["details"] is False and page["bar"] == "app-bar"


def test_details_left_open_is_shut_when_the_reader_comes_back_to_the_screen() -> None:
    """The browser's Back and Forward change the view with no press and no focus to close the
    menu; the company page draws no Details, and it must not stand open on the Screen again."""
    _, opened, page, back = _trace(
        [LANDED, {"do": "details"}, _show("company", "AAPL"), _show("screen")]
    )
    assert opened["menu"] is True
    assert page["details"] is False and page["menu"] is False
    assert back["details"] is True and back["menu"] is False


def test_the_bare_bar_has_no_margins() -> None:
    page = " ".join(_static_file("index.html").split())
    assert ".app-bar--bare { margin: 0; }" in page
    assert ".app-bar--bare .app-status { margin: 0; }" in page


def test_no_page_draws_a_link_back_to_the_screen() -> None:
    """The header's Screen view is the way back from every page, and the browser's Back returns
    to the view left: the company page draws no link of its own, and the stylesheet keeps no
    rule for one."""
    for script in sorted(STATIC.glob("*.js")):
        assert "Back to the screen" not in script.read_text(), script.name
    page = _static_file("index.html")
    assert "__back" not in page


def test_after_a_moat_write_the_line_details_and_the_stamp_stay_the_run_before() -> None:
    """A moat write values one company again, and the refresh route answers that revalue as
    ``last`` and the run before it as ``shown``. The line, Details and the header's stamp describe
    ``shown``: the last run of the whole screen (the founder, 2026-11-22)."""
    write = LAST["last"] | {
        "id": 67,
        "kind": "revalue",
        "startedAt": "2026-11-17T09:00:00+00:00",
        "finishedAt": "2026-11-17T09:00:01+00:00",
        "calibration": None,
    }
    body = {"refresh": None, "last": write, "shown": LAST["last"], "error": None}
    [plain] = _trace([LANDED])
    [written] = _trace([{"do": "answer", "url": CURRENT, "status": 200, "body": body}])
    assert written["status"] == plain["status"]
    assert written["status"].startswith("full done ") and written["status"].endswith(LINE_END)
    assert written["details"] is True
    assert written["ran"] is not None and written["ran"] == plain["ran"]
