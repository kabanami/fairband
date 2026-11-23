"""The header and the status line under it across the views (the company page's design, the
founder's rulings of 2026-11-17). The line of the last refresh and its Details describe the whole
universe, so the Screen and the other views of many companies keep them; the company page, a page
of one company, draws neither: the header's stamp already says when the engine ran. A refresh
that runs still draws its bar there, and a notice its sentence, since the header has neither.
The header's finder stands in its right slot on every view but the Screen, whose table has a
field of its own. The menu is in the founder's order, and a group's name in Statistics opens the
Screen on its filter (spec 2026-11-23 refresh experience, 4.5 and 4.6). The page follows every
run that ends, whoever started it: it asks the refresh's state every 30 seconds while no run is
alive, and reads again what a run that ended may have changed; only a run of the whole screen
fades the panels (4.1 and 4.3). The bundle, app.js, finder.js and controls.js run in node
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
        "symbols": None,
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
# The 20 newest runs, the newest first: here the one.
LAST["recent"] = [{"id": 66, "kind": "full", "symbols": None, "status": "done"}]
RUNNING: dict[str, Any] = {
    "refresh": {
        "id": 67,
        "kind": "full",
        "symbols": None,
        "stage": "fetch",
        "done": 40,
        "failed": 0,
        "remaining": 1529,
        "current": "AAPL",
    }
}
LANDED = {"do": "answer", "url": CURRENT, "status": 200, "body": LAST}
RUN_ALIVE = {"do": "answer", "url": CURRENT, "status": 200, "body": RUNNING}
LINE_END = " · 1,371 of 1,569 valued · 1 failed"
# The screen's rows, the few keys the Screen's filters read, and its first read's address.
ROWS = [
    {"ticker": "AAA", "name": "AAA Co", "sector": "Technology", "industry": "Software"},
    {"ticker": "BBB", "name": "BBB Co", "sector": "Technology", "industry": "Hardware"},
    {"ticker": "CCC", "name": "CCC Co", "sector": "Energy", "industry": "Oil"},
    {"ticker": "DDD", "name": "DDD Co", "sector": None, "industry": None},
]
SCREEN = {
    "do": "answer",
    "url": "/api/screen?sort=ticker&dir=asc",
    "status": 200,
    "body": {"rows": [row | {"phase": 4, "capBand": "Mid", "watchlists": []} for row in ROWS]},
}
# The design system's EMPTY_FILTERS: nothing narrowed.
EMPTY_FILTERS: dict[str, Any] = {
    "designation": [],
    "stance": [],
    "phase": [],
    "cap": [],
    "sector": [],
    "industry": [],
    "watchlist": [],
    "reviewedOnly": False,
    "hideExpired": False,
}
# The reader's own FIND and filters on the Screen, which a group's filter clears.
CHOSEN = {
    "do": "table",
    "query": "aa",
    "filters": EMPTY_FILTERS | {"phase": [5], "hideExpired": True},
}
STATISTICS = "/api/statistics?by=sector"
GROUP = {"valued": 0, "medianPriceToValue": None, "shareBelowValue": None}
BY_SECTOR = {
    "do": "answer",
    "url": STATISTICS,
    "status": 200,
    "body": {
        "by": "sector",
        "groups": [
            GROUP | {"name": "Energy", "count": 1, "filter": {"sector": ["Energy"]}},
            GROUP | {"name": "Technology", "count": 2, "filter": {"sector": ["Technology"]}},
            GROUP | {"name": "none", "count": 1, "filter": None},
        ],
    },
}


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


TICK = {"do": "tick"}
RUN_66 = LAST["recent"][0]
DETAIL = "/api/companies/MGCO"  # the company page's read as it opens, MGCO shown


def _run(
    run_id: int, kind: str, symbols: list[str] | None = None, status: str = "done"
) -> dict[str, Any]:
    """One entry of the refresh state's ``recent``, as the server answers it."""
    return {"id": run_id, "kind": kind, "symbols": symbols, "status": status}


def _idle(*recent: dict[str, Any]) -> dict[str, Any]:
    """The refresh state with no run alive, after the runs ``recent``, the newest first: the last
    run is the newest of them, and the line describes run 66 (``shown``)."""
    newest = {key: recent[0][key] for key in ("id", "kind", "symbols", "status")}
    body = {
        "refresh": None,
        "last": LAST["last"] | newest,
        "shown": LAST["last"],
        "error": None,
        "recent": list(recent),
    }
    return {"do": "answer", "url": CURRENT, "status": 200, "body": body}


def _alive(run_id: int, kind: str, symbols: list[str] | None) -> dict[str, Any]:
    """The refresh state while the run ``run_id`` is alive."""
    body = {"refresh": RUNNING["refresh"] | {"id": run_id, "kind": kind, "symbols": symbols}}
    return {"do": "answer", "url": CURRENT, "status": 200, "body": body}


def _visible(shown: bool) -> dict[str, Any]:
    return {"do": "visibility", "hidden": not shown}


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


@pytest.mark.parametrize("view", ["statistics", "watchlists", "methodology", "settings", "inbox"])
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
    recent = [LAST["recent"][0] | {"status": status}]
    body = {"refresh": None, "last": last, "shown": last, "error": None, "recent": recent}
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
        "symbols": ["MGCO"],
        "startedAt": "2026-11-17T09:00:00+00:00",
        "finishedAt": "2026-11-17T09:00:01+00:00",
        "calibration": None,
    }
    recent = [_run(67, "revalue", ["MGCO"]), *LAST["recent"]]
    body = {"refresh": None, "last": write, "shown": LAST["last"], "error": None, "recent": recent}
    [plain] = _trace([LANDED])
    [written] = _trace([{"do": "answer", "url": CURRENT, "status": 200, "body": body}])
    assert written["status"] == plain["status"]
    assert written["status"].startswith("full done ") and written["status"].endswith(LINE_END)
    assert written["details"] is True
    assert written["ran"] is not None and written["ran"] == plain["ran"]


def test_the_menu_is_in_the_founders_order() -> None:
    """Spec 2026-11-23 refresh experience, 4.6: Screen, Watchlists, Statistics, Methodology,
    Settings, Inbox. Statistics is the view Groups was, at its own address (4.5)."""
    _, shown = _trace([LANDED, _show("statistics")])
    assert shown["views"] == [
        ["screen", "Screen"],
        ["watchlists", "Watchlists"],
        ["statistics", "Statistics"],
        ["methodology", "Methodology"],
        ["settings", "Settings"],
        ["inbox", "Inbox"],
    ]
    assert (shown["view"], shown["hash"]) == ("statistics", "#statistics")


def test_the_old_groups_address_opens_statistics() -> None:
    """4.5: a bookmark or a link to #groups opens Statistics, which reads its groups, and the
    address is put right."""
    opened, read = _trace([{"do": "hash", "hash": "#groups"}, BY_SECTOR])
    assert (opened["view"], opened["hash"]) == ("statistics", "#statistics")
    assert [name for name, _ in read["statistics"]] == ["Energy", "Technology", "none"]


def test_a_group_s_name_opens_the_screen_on_its_filter() -> None:
    """4.5: FairbandPage.filterScreen opens the Screen with the group's filter over the empty
    filters, the reader's other filters and FIND cleared. An industry comes with its sectors; one
    the chosen sectors' rows do not list goes, as the Filters menu drops it (listedFilters)."""
    loaded, chosen, _, technology, software, unlisted = _trace(
        [
            SCREEN,
            CHOSEN,
            _show("statistics"),
            {"do": "filter", "filter": {"sector": ["Technology"]}},
            {"do": "filter", "filter": {"sector": ["Technology"], "industry": ["Software"]}},
            {"do": "filter", "filter": {"sector": ["Energy"], "industry": ["Software"]}},
        ]
    )
    assert (loaded["find"], loaded["filters"]) == ("", EMPTY_FILTERS)
    assert (chosen["find"], chosen["filters"]) == ("aa", CHOSEN["filters"])
    assert (technology["view"], technology["hash"]) == ("screen", "")
    assert technology["find"] == ""
    assert technology["filters"] == EMPTY_FILTERS | {"sector": ["Technology"]}
    assert software["filters"] == EMPTY_FILTERS | {
        "sector": ["Technology"],
        "industry": ["Software"],
    }
    assert unlisted["filters"] == EMPTY_FILTERS | {"sector": ["Energy"]}


def test_a_group_s_name_is_a_link_and_none_is_plain_text() -> None:
    """4.5: each name with a filter is a link to the page's own path, whose press stays on the
    page and opens the Screen on the group; ``none`` has no filter and is plain text."""
    *_, read, followed = _trace(
        [SCREEN, CHOSEN, _show("statistics"), BY_SECTOR, {"do": "follow", "name": "Technology"}]
    )
    assert read["statistics"] == [["Energy", "/"], ["Technology", "/"], ["none", None]]
    assert followed["prevented"] is True
    assert (followed["view"], followed["find"]) == ("screen", "")
    assert followed["filters"] == EMPTY_FILTERS | {"sector": ["Technology"]}


def test_a_run_the_page_did_not_start_is_followed() -> None:
    """An agent's research revalues its company after a scoped refresh of it, and neither run is
    alive at any of the page's reads. The page asks every 30 seconds while no run is alive; an
    answer with runs newer than the one its rows were read under reads the rows again, and the
    next, with none newer, reads nothing (spec 2026-11-23 refresh experience, 4.3). A run of
    named companies fades nothing (4.1)."""
    ended = _idle(_run(68, "revalue", ["MSCO"]), _run(67, "scoped", ["MSCO"]), RUN_66)
    landed, asked, followed, _, again = _trace([LANDED, TICK, ended, TICK, ended])
    assert (landed["reads"], landed["waits"]) == ([], [30000])
    assert asked["reads"] == [CURRENT]
    assert (followed["reads"], followed["waits"]) == ([SCREEN["url"]], [30000])
    assert followed["run"] is False and followed["recomputing"] is False
    assert again["reads"] == []


def test_the_first_answer_follows_no_run() -> None:
    """The rows the page reads as it loads already hold the runs that ended before: its first
    answer only sets the run they were read under."""
    ended = _idle(_run(68, "revalue", ["MSCO"]), _run(67, "price"), RUN_66)
    first, _, second = _trace([ended, TICK, ended])
    assert (first["reads"], first["waits"]) == ([], [30000])
    assert second["reads"] == []


def test_a_run_alive_as_the_page_loads_is_followed_at_its_end() -> None:
    *_, ended = _trace([RUN_ALIVE, TICK, _idle(_run(67, "full"), RUN_66)])
    assert ended["reads"] == [SCREEN["url"]]


def test_the_statistics_are_read_again_where_that_view_shows() -> None:
    *_, followed = _trace([LANDED, _show("statistics"), TICK, _idle(_run(67, "price"), RUN_66)])
    assert followed["reads"] == [SCREEN["url"], STATISTICS]


def test_a_company_page_is_read_again_only_for_its_own_company() -> None:
    """4.3: a run covers the company page's company where it names it or is a run of the whole
    screen; a page whose company the run did not cover is left as it is, so a reader is not
    moved. The rows are read again all the same."""
    other = _run(67, "scoped", ["MSCO"])
    own = _run(68, "revalue", ["MGCO"])
    whole = _run(69, "price")
    _, page, _, after_other, _, after_own, _, after_whole = _trace(
        [
            LANDED,
            _show("company", "MGCO"),
            TICK,
            _idle(other, RUN_66),
            TICK,
            _idle(own, other, RUN_66),
            TICK,
            _idle(whole, own, other, RUN_66),
        ]
    )
    assert page["reads"] == [DETAIL]
    assert after_other["reads"] == [SCREEN["url"]]
    assert after_own["reads"] == [SCREEN["url"], DETAIL]
    assert after_whole["reads"] == [SCREEN["url"], DETAIL]


@pytest.mark.parametrize(("kind", "symbols"), [("scoped", ["MSCO"]), ("revalue", ["MGCO"])])
def test_a_run_of_named_companies_fades_nothing(kind: str, symbols: list[str]) -> None:
    """4.1: a scoped refresh and a revalue of named companies (an agent's, a moat write's) fade
    no panel. The run bar and Cancel stand as for any run, and the page asks every 2 seconds
    while it is alive, then every 30 again."""
    *_, alive, _, ended = _trace(
        [LANDED, TICK, _alive(67, kind, symbols), TICK, _idle(_run(67, kind, symbols), RUN_66)]
    )
    assert alive["run"] is True and alive["actions"] == ["Cancel"]
    assert (alive["recomputing"], alive["waits"]) == (False, [2000])
    assert (ended["reads"], ended["waits"]) == ([SCREEN["url"]], [30000])


@pytest.mark.parametrize("kind", ["price", "full", "revalue"])
def test_a_run_of_the_whole_screen_fades_the_panels_until_it_ends(kind: str) -> None:
    *_, alive, _, ended = _trace(
        [LANDED, TICK, _alive(67, kind, None), TICK, _idle(_run(67, kind), RUN_66)]
    )
    assert alive["recomputing"] is True and alive["run"] is True
    assert ended["recomputing"] is False and ended["reads"] == [SCREEN["url"]]


def test_a_hidden_page_does_not_ask_and_asks_at_once_when_shown() -> None:
    """4.3: no read while the page is hidden; shown again, it reads at once, the refresh's state
    and the Inbox's count, and the 30-second cycle runs again from the answer."""
    _, hidden, ticked, shown, landed = _trace(
        [LANDED, _visible(False), TICK, _visible(True), LANDED]
    )
    assert (hidden["reads"], hidden["waits"]) == ([], [30000])
    assert (ticked["reads"], ticked["waits"]) == ([], [])
    assert shown["reads"] == [CURRENT, "/api/inbox"]
    assert landed["waits"] == [30000]


@pytest.mark.parametrize(("seen", "missing"), [(10, True), (20, False)])
def test_runs_past_the_list_read_everything_again(seen: int, missing: bool) -> None:
    """4.3, and the plan's review focus 2: ``recent`` holds the 20 newest runs. Read under run
    10, the page finds runs 40 to 21, each naming another company than the one it shows: runs 11
    to 20 are missing and may have covered it, so they are followed as one run of the whole
    screen, and the company page is read again. Read under run 20, none is missing."""
    named = [_run(run_id, "scoped", ["MSCO"]) for run_id in range(40, 20, -1)]
    *_, followed = _trace(
        [_idle(_run(seen, "full")), _show("company", "MGCO"), TICK, _idle(*named)]
    )
    assert followed["reads"] == [SCREEN["url"], *([DETAIL] if missing else [])]


@pytest.mark.parametrize("at_load", [True, False])
def test_a_run_another_process_runs_is_followed_at_its_end(at_load: bool) -> None:
    """A run of the command-line tool, in another process, has no progress on the server: the
    state answers no run alive, and the run's entry in ``recent`` says ``running``. Such an entry
    is not followed, nor passed: it reads nothing, draws no bar and fades nothing, and the next
    answer, where it is done, reads the Screen again; so too where it ran as the page loaded."""
    running = _idle(_run(67, "full", status="running"), RUN_66)
    ended = _idle(_run(67, "full"), RUN_66)
    *_, during, _, after = _trace(
        [running, TICK, ended] if at_load else [LANDED, TICK, running, TICK, ended]
    )
    assert during["reads"] == [] and during["run"] is False and during["recomputing"] is False
    assert after["reads"] == [SCREEN["url"]]


SCREEN_URL = SCREEN["url"]
MANY = 1546  # the screen's rows in the count's tests, past a thousand


def _rows(moved: int = 0, revalued: int = 0) -> list[dict[str, Any]]:
    """The screen's ``MANY`` rows, the first ``moved`` a dollar dearer than at the start and the
    first ``revalued`` a dollar more valuable."""
    return [
        {
            "ticker": f"T{n:04d}",
            "name": f"T{n:04d} Co",
            "price": 11.0 if n < moved else 10.0,
            "fairValue": 21.0 if n < revalued else 20.0,
            "watchlists": [],
        }
        for n in range(MANY)
    ]


def _screen(rows: list[dict[str, Any]], url: str = SCREEN_URL) -> dict[str, Any]:
    return {"do": "answer", "url": url, "status": 200, "body": {"rows": rows}}


def _ended_run(kind: str, symbols: list[str] | None, status: str) -> dict[str, Any]:
    """The refresh's state after run 67 ended: the line describes it, a price refresh with its
    repriced count, a full refresh or a revalue with the calibration of run 66, a run that did
    not end done with its message."""
    calibration: dict[str, Any] | None = LAST["last"]["calibration"]
    if kind == "price":
        calibration = {"repriced": MANY, "total": MANY, "failed": 0, "skipped": 0}
    if status != "done" or symbols is not None:
        calibration = None
    last = LAST["last"] | {
        "id": 67,
        "kind": kind,
        "symbols": symbols,
        "status": status,
        "calibration": calibration,
        "message": None if status == "done" else "no company was admitted",
    }
    recent = [_run(67, kind, symbols, status), RUN_66]
    body = {"refresh": None, "last": last, "shown": last, "error": None, "recent": recent}
    return {"do": "answer", "url": CURRENT, "status": 200, "body": body}


@pytest.mark.parametrize(
    ("kind", "symbols", "status", "moved", "revalued", "words"),
    [
        ("price", None, "done", MANY, 0, "1,546 prices changed"),
        ("full", None, "done", MANY, 37, "1,546 prices changed, 37 values changed"),
        ("revalue", None, "done", 0, 1, "1 value changed"),
        ("price", None, "done", 0, 0, "no price changed"),
        ("full", None, "done", 0, 0, "no figure changed"),
        ("scoped", ["T0000"], "done", 1, 0, None),
        ("full", None, "failed", MANY, 0, None),
    ],
)
def test_a_whole_run_that_ended_done_adds_its_count(
    kind: str,
    symbols: list[str] | None,
    status: str,
    moved: int,
    revalued: int,
    words: str | None,
) -> None:
    """4.2: after a run of the whole screen that ended done, the status line counts what the
    page's own comparison found, in the tint the changed cells take; a price refresh that moved
    nothing says no price changed. A run of named companies and a run that did not end done add
    no sentence. The count's words stand after the marks are taken off (MARK_MS), until the next
    run; its tint goes with the marks, so it plays once: drawn again, back from the company page,
    which draws no line, the count has none."""
    *_, landed, ticked, page, back = _trace(
        [
            LANDED,
            _screen(_rows()),
            TICK,
            _ended_run(kind, symbols, status),
            _screen(_rows(moved, revalued)),
            TICK,
            _show("company", "MGCO"),
            _show("screen"),
        ]
    )
    assert page["changes"] is None
    for step in (landed, ticked, back):
        if words is None:
            assert step["changes"] is None and step["tinted"] is None
            assert "changed" not in step["status"]
        else:
            assert step["status"].endswith(" · " + words)
            assert step["changes"] == words
    if words is not None:
        assert (landed["tinted"], ticked["tinted"], back["tinted"]) == (True, False, False)


def test_the_rows_a_run_changed_are_marked_until_the_marks_are_taken_off() -> None:
    """4.2: the rows that land after a run ended are marked against those the page held, by
    ticker, a new row not at all; 1.3 seconds on (MARK_MS), past the tint's 1.2, the marks are
    taken off in one draw. A read of the rows that is not a run's end (a sort) marks nothing."""
    before = [{"ticker": t, "price": 10.0, "watchlists": []} for t in ("AAA", "BBB")]
    after = [
        {"ticker": "AAA", "price": 10.0, "watchlists": []},
        {"ticker": "BBB", "price": 9.0, "watchlists": []},
        {"ticker": "CCC", "price": 30.0, "watchlists": []},
    ]
    dearer = [row | {"price": row["price"] + 1} for row in after]
    desc = "/api/screen?sort=ticker&dir=desc"
    *_, landed, ticked, _, sorted_ = _trace(
        [
            LANDED,
            _screen(before),
            TICK,
            _idle(_run(67, "price"), RUN_66),
            _screen(after),
            TICK,
            {"do": "sort", "column": "ticker"},
            _screen(dearer, desc),
        ]
    )
    assert landed["marked"] == [["BBB", -1]]
    assert landed["waits"] == [30000, 1300, 1300]  # the marks, then the count's tint
    assert ticked["marked"] == [] and ticked["waits"] == []
    assert sorted_["marked"] == [] and sorted_["waits"] == []


def test_the_list_s_own_read_marks_its_rows() -> None:
    """The watchlist page reads its rows in its own sort where it differs from the Screen's (spec
    2026-11-22 7.1): that read, after a run ended, marks them the same way."""
    lists = [{"id": 1, "name": "Core", "symbols": [{"symbol": "AAA"}, {"symbol": "BBB"}]}]
    before = [{"ticker": t, "price": 10.0, "watchlists": [1]} for t in ("BBB", "AAA")]
    after = [
        {"ticker": "BBB", "price": 12.0, "watchlists": [1]},
        {"ticker": "AAA", "price": 10.0, "watchlists": [1]},
    ]
    desc = "/api/screen?sort=ticker&dir=desc"
    trace = _trace(
        [
            LANDED,
            _screen(list(reversed(before))),
            {"do": "answer", "url": "/api/watchlists", "status": 200, "body": lists},
            _show("watchlists"),
            {"do": "list", "id": 1},
            {"do": "sort", "column": "ticker"},
            _screen(before, desc),
            TICK,
            _idle(_run(67, "price"), RUN_66),
            _screen(after, desc),
            TICK,
        ]
    )
    sorted_, landed, ticked = trace[6], trace[9], trace[10]
    assert sorted_["reads"] == [] and sorted_["marked"] == []
    assert trace[8]["reads"] == [SCREEN_URL, desc]
    assert landed["marked"] == [["BBB", 1]]
    assert ticked["marked"] == []


def test_a_failed_read_asks_again_on_the_cycle_and_says_when() -> None:
    """A read of the refresh's state that fails is asked again all the same: in 30 seconds with
    no run alive, in 2 while one is."""
    failed = {"do": "answer", "url": CURRENT, "status": 500, "body": {"detail": "locked"}}
    idle, _, _, _, alive = _trace([failed, TICK, RUN_ALIVE, TICK, failed])
    assert idle["waits"] == [30000]
    assert idle["notice"].endswith(". The page asks again every 30 seconds.")
    assert alive["waits"] == [2000]
    assert alive["notice"].endswith(". The page asks again every 2 seconds.")
