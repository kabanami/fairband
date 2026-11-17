"""The header and the status line under it across the views (the company page's design, the
founder's rulings of 2026-11-17). The line of the last refresh and its Details describe the whole
universe, so the Screen and the other views of many companies keep them; the company page and the
report page, each a page of one company, draw neither: the header's stamp already says when the
engine ran. A refresh that runs still draws its bar there, and a notice its sentence, since the
header has neither. The header's finder stands in its right slot on every view but the Screen,
whose table has a field of its own. The bundle, app.js, finder.js and controls.js run in node
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


@pytest.mark.parametrize("view", ["company", "report"])
def test_a_page_of_one_company_draws_no_last_line_and_no_details(view: str) -> None:
    """The status region stays, empty, so a run that starts is announced from a region the page
    already had; the header marks no view; back on the Screen the line and Details return."""
    _, page, screen = _trace([LANDED, _show(view, "AAPL"), _show("screen")])
    assert page["view"] == ""
    assert page["status"] == "" and page["details"] is False
    assert page["run"] is False and page["notice"] is None
    assert page["finder"] is True
    assert screen["status"].endswith(LINE_END) and screen["details"] is True
    assert screen["finder"] is False


@pytest.mark.parametrize("view", ["groups", "watchlists", "methodology", "settings", "inbox"])
def test_a_view_of_many_companies_keeps_the_line_and_has_the_finder(view: str) -> None:
    _, shown = _trace([LANDED, _show(view)])
    assert shown["view"] == view
    assert shown["status"].endswith(LINE_END) and shown["details"] is True
    assert shown["finder"] is True


@pytest.mark.parametrize("view", ["company", "report"])
def test_a_running_refresh_draws_its_bar_on_a_page_of_one_company(view: str) -> None:
    """The header has no bar of its own, so the run's progress and its Cancel stay where they
    are on every view."""
    _, page = _trace(
        [{"do": "answer", "url": CURRENT, "status": 200, "body": RUNNING}, _show(view, "AAPL")]
    )
    assert page["run"] is True and page["details"] is False
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
    assert failed["status"] == ""
    assert failed["notice"].startswith("The refresh status did not load: ")
    assert screen["status"] == "No refresh has run yet." and screen["notice"] == failed["notice"]


def test_the_bar_takes_no_room_while_it_draws_nothing() -> None:
    """Read as text: the bar with no line, no run and no notice is marked, and the mark takes its
    margins away, so a page of one company starts right under the header."""
    controls = _static_file("controls.js")
    assert "className: 'app-bar' + (bare ? ' app-bar--bare' : '')" in controls
    page = " ".join(_static_file("index.html").split())
    assert ".app-bar--bare { margin: 0; }" in page
    assert ".app-bar--bare .app-status { margin: 0; }" in page


def test_no_page_draws_a_link_back_to_the_screen() -> None:
    """The header's Screen view is the way back from every page, and the browser's Back returns
    to the view left: the company page and the report page draw no link of their own, and the
    stylesheet keeps no rule for one."""
    for script in sorted(STATIC.glob("*.js")):
        assert "Back to the screen" not in script.read_text(), script.name
    page = _static_file("index.html")
    assert "__back" not in page
