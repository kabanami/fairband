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
fades the panels (4.1 and 4.3), and only such a run that the page started, the reader's own
press, locks the page under the refresh layer until it ends, or until the reader keeps reading on
a long run (4.1). The bundle, app.js, finder.js and controls.js run in node
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


def _trace(
    steps: list[dict[str, Any]],
    storage: dict[str, str] | str | None = None,
    hidden: bool = False,
) -> list[dict[str, Any]]:
    """The trace of ``steps`` on a page loaded with the tab's session storage ``storage``: its
    entries, as a reload finds them, ``"throws"`` where the browser refuses it, or empty; with
    ``hidden``, a page loaded in a hidden tab."""
    assert NODE is not None
    given = {"steps": steps, "storage": {} if storage is None else storage, "hidden": hidden}
    done = subprocess.run(
        [NODE, str(DRIVER), str(BUNDLE)]
        + [str(STATIC / name) for name in ("app.js", "finder.js", "controls.js")],
        input=json.dumps(given),
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


def test_a_page_loaded_hidden_asks_once_at_load() -> None:
    """A page loaded in a hidden tab (a browser restores its background tabs hidden) asks for the
    refresh's state once as it loads, so it knows the run its rows were read under; the later
    reads wait for it to show (4.3). A run that ends while it is still hidden is followed when it
    shows: its rows are read again."""
    landed, ticked, shown, followed = _trace(
        [LANDED, TICK, _visible(True), _idle(_run(67, "price"), RUN_66)], hidden=True
    )
    assert landed["waits"] == [30000]
    assert (ticked["reads"], ticked["waits"]) == ([], [])
    assert shown["reads"] == [CURRENT, "/api/inbox"]
    assert followed["reads"] == [SCREEN["url"]]


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
    is not followed, nor passed: it reads nothing, draws no bar, fades nothing and locks nothing
    (4.1: the layer is for a run the server reports alive), and the next answer, where it is done,
    reads the Screen again; so too where it ran as the page loaded."""
    running = _idle(_run(67, "full", status="running"), RUN_66)
    ended = _idle(_run(67, "full"), RUN_66)
    *_, during, _, after = _trace(
        [running, TICK, ended] if at_load else [LANDED, TICK, running, TICK, ended]
    )
    assert during["reads"] == [] and during["run"] is False and during["recomputing"] is False
    assert during["layer"]["on"] is False and during["inert"] == [False] * 4
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


PRICED = [{"ticker": t, "price": 10.0, "watchlists": []} for t in ("AAA", "BBB", "CCC")]
DESC = "/api/screen?sort=ticker&dir=desc"


def _priced(**prices: float) -> list[dict[str, Any]]:
    """The three rows of PRICED, newest sort first (ticker desc), with ``prices`` over theirs."""
    return [row | {"price": prices.get(row["ticker"], row["price"])} for row in PRICED[::-1]]


def test_a_run_s_end_marks_against_the_rows_from_before_the_run() -> None:
    """4.2, the final review's round: a read of the rows in a run's middle (here a sort, which
    Keep reading or a run the page did not start leaves open, as does a watchlist write) brings in
    rows the run already rewrote. The end marks and counts against the rows the page held as the
    run was first seen alive (FairbandPage.baseline), not against those, so the count is the
    run's whole."""
    *_, middle, _, _, landed = _trace(
        [
            LANDED,
            _screen(PRICED),
            TICK,
            _alive(67, "price", None),
            {"do": "sort", "column": "ticker"},
            _screen(_priced(BBB=9.0), DESC),
            TICK,
            _ended_run("price", None, "done"),
            _screen(_priced(BBB=9.0, CCC=12.0), DESC),
        ]
    )
    assert middle["marked"] == []
    assert landed["marked"] == [["CCC", 1], ["BBB", -1]]
    assert landed["changes"] == "2 prices changed"


def test_a_read_started_just_after_a_run_s_end_lands_marked() -> None:
    """A read of the rows started in the moment between a run's end and its rows landing (a sort)
    overtakes the marked read, whose answer is dropped: the mark is handed on, so the rows that
    land are marked, with the count."""
    *_, ended, _, dropped, landed = _trace(
        [
            LANDED,
            _screen(PRICED),
            TICK,
            _ended_run("price", None, "done"),
            {"do": "sort", "column": "ticker"},
            _screen(PRICED, SCREEN_URL),
            _screen(_priced(BBB=9.0, CCC=12.0), DESC),
        ]
    )
    assert ended["reads"] == [SCREEN_URL]
    assert dropped["marked"] == [] and dropped["changes"] is None
    assert landed["marked"] == [["CCC", 1], ["BBB", -1]]
    assert landed["changes"] == "2 prices changed"


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


# The refresh layer (spec 2026-11-23 refresh experience, 4.1).
LOCKED = "The page is locked until the refresh ends."
KEPT = LOCKED + " Keep reading removes the lock; the refresh goes on."
KEEP = {"do": "press", "name": "Keep reading"}
CANCEL = {"do": "press", "name": "Cancel"}
ESCAPE = {"do": "key", "key": "Escape"}
FREE = [False] * 4  # main.app-page and the three mounts app.js appends beside it, none inert
HELD = [True] * 4  # each of them inert
CANCEL_URL = "/api/refresh/cancel"
START_URL = "/api/refresh"
MINE = "fairband.refresh.mine"  # the tab's session storage: the id of the page's own run
BUTTONS = {"price": "Refresh prices", "full": "Refresh all"}


def _mine(run_id: int, kind: str) -> list[dict[str, Any]]:
    """The page starts the run ``run_id`` itself: for a price or a full refresh the reader presses
    the header's button and the server answers the run's id; for a whole revalue, the Settings
    view's Revalue now, which hands the header the id its answer gave
    (``FairbandPage.followRefresh``). Either way the refresh's state is read at once."""
    if kind == "revalue":
        return [{"do": "followRefresh", "id": run_id}]
    return [
        {"do": "start", "name": BUTTONS[kind]},
        {"do": "answer", "url": START_URL, "status": 200, "body": {"refreshId": run_id}},
    ]


@pytest.mark.parametrize(
    ("kind", "title", "sentence"),
    [
        ("price", "Refreshing prices", LOCKED),
        ("full", "Refreshing all", KEPT),
        ("revalue", "Revaluing", KEPT),
    ],
)
def test_the_page_s_own_whole_run_locks_the_page(kind: str, title: str, sentence: str) -> None:
    """A run of the whole screen the page started, the reader's press, draws the layer over the
    page: a modal dialog labelled by its title, the run bar, the sentence and Cancel. Every child
    of the body but the layer is inert, main.app-page and the mounts beside it, and the popups
    close as the layer turns on, once. The panel itself takes the focus as it turns on, not a
    button, so a key pressed by reflex neither cancels the run nor lifts the lock; drawn again
    under the same lock, it does not take it again. Before the run the layer is drawn off, empty,
    inert and hidden from a screen reader. The run's id is kept in the tab's session storage."""
    trace = _trace([LANDED, *_mine(67, kind), _alive(67, kind, None), TICK, _alive(67, kind, None)])
    landed, locked, again = trace[0], trace[-3], trace[-1]
    assert landed["layer"] == {
        "on": False,
        "dialog": False,
        "hidden": "true",
        "inert": True,
        "panel": False,
        "title": None,
        "bar": False,
        "stage": None,
        "sentence": None,
        "keep": False,
        "cancel": None,
        "notice": None,
    }
    assert landed["inert"] == FREE and landed["focused"] is False
    layer = locked["layer"]
    assert (layer["on"], layer["dialog"], layer["hidden"], layer["inert"]) == (
        True,
        True,
        None,
        False,
    )
    assert (layer["panel"], layer["title"], layer["bar"], layer["stage"]) == (
        True,
        title,
        True,
        None,
    )
    assert layer["cancel"] == "enabled" and layer["notice"] is None
    assert layer["sentence"] == sentence
    assert locked["inert"] == HELD and locked["closed"] == 1 and locked["focused"] is True
    assert locked["storage"] == {MINE: "67"}
    assert again["layer"] == layer and again["inert"] == HELD and again["closed"] == 0
    assert again["focused"] is False


@pytest.mark.parametrize("kind", ["price", "full", "revalue"])
def test_a_whole_run_the_page_did_not_start_draws_no_layer(kind: str) -> None:
    """Claude's ruling at the final review, 2026-11-24: the lock is for the reader's own press,
    since the research playbook has an agent start runs of the whole screen, and a lock or a
    darkening the reader did not start is the design's anti-goal. A whole run the page did not
    start, an agent's or another tab's, alive as the page loads or seen later, draws no layer and
    makes nothing inert; the page is as under a run before the layer: the panels faint, the run
    bar in the status line and Cancel in the header. Its end is followed and marked, with the
    count (4.2 and 4.3)."""
    alive = _alive(67, kind, None)
    [loaded] = _trace([alive])
    *_, seen, _, ended, landed = _trace(
        [
            LANDED,
            _screen(_rows()),
            TICK,
            alive,
            TICK,
            _ended_run(kind, None, "done"),
            _screen(_rows(MANY)),
        ]
    )
    for step in (loaded, seen):
        assert step["layer"]["on"] is False and step["layer"]["hidden"] == "true"
        assert step["inert"] == FREE and step["closed"] == 0 and step["focused"] is False
        assert (step["recomputing"], step["run"], step["actions"]) == (True, True, ["Cancel"])
        assert step["storage"] == {}
    assert ended["reads"] == [SCREEN_URL] and ended["layer"]["on"] is False
    assert landed["changes"] == "1,546 prices changed"


def test_a_reload_during_the_page_s_own_run_locks_again() -> None:
    """The run's id is kept for the browser tab, in its session storage, and read as the script
    loads: the page loaded again while its own run is alive locks again, after Keep reading too,
    since Keep reading is the page's own state (4.1). The page that wrote the id keeps it in
    memory as well, so its storage emptied does not lift its lock; a page loaded on another id
    locks nothing."""
    *_, locked, kept = _trace([LANDED, *_mine(67, "full"), _alive(67, "full", None), KEEP])
    assert locked["layer"]["on"] is True and kept["layer"]["on"] is False
    assert kept["storage"] == {MINE: "67"}
    [reloaded] = _trace([RUN_ALIVE], storage=kept["storage"])
    assert reloaded["layer"]["on"] is True and reloaded["inert"] == HELD
    assert reloaded["layer"]["title"] == "Refreshing all" and reloaded["focused"] is True
    [other] = _trace([RUN_ALIVE], storage={MINE: "66"})
    assert other["layer"]["on"] is False and other["inert"] == FREE
    *_, cleared, _, again = _trace(
        [
            LANDED,
            *_mine(67, "price"),
            _alive(67, "price", None),
            {"do": "storage", "clear": True},
            TICK,
            _alive(67, "price", None),
        ]
    )
    assert cleared["storage"] == {}
    assert again["layer"]["on"] is True and again["inert"] == HELD


def test_with_a_storage_that_throws_the_lock_lives_in_memory() -> None:
    """Where the browser refuses the storage (a private window, blocked site data), as the page
    loads or as it writes, the page keeps its run's id in memory: its own run locks all the same,
    and a reload, which finds no id, locks nothing."""
    *_, locked, _, again = _trace(
        [LANDED, *_mine(67, "price"), _alive(67, "price", None), TICK, _alive(67, "price", None)],
        storage="throws",
    )
    assert locked["layer"]["on"] is True and locked["inert"] == HELD
    assert again["layer"]["on"] is True and again["storage"] == "throws"
    *_, refused = _trace(
        [LANDED, {"do": "storage", "throws": True}, *_mine(67, "full"), _alive(67, "full", None)]
    )
    assert refused["layer"]["on"] is True and refused["inert"] == HELD
    [reloaded] = _trace([RUN_ALIVE], storage="throws")
    assert reloaded["layer"]["on"] is False and reloaded["inert"] == FREE


def test_a_run_the_page_asked_for_and_did_not_start_locks_nothing() -> None:
    """The Settings view's Revalue now hands the header the id of the revalue its answer gave
    (``FairbandPage.followRefresh(id)``), so that whole revalue is the page's own and locks.
    After a 409, a run already running that the page did not start, it hands none: the run is
    followed with no lock, and its end reads the rows again. The header's own press answered 409
    keeps no id either."""
    *_, own = _trace([LANDED, {"do": "followRefresh", "id": 67}, _alive(67, "revalue", None)])
    assert own["layer"]["on"] is True and own["layer"]["title"] == "Revaluing"
    assert own["storage"] == {MINE: "67"}
    *_, other, _, ended = _trace(
        [
            LANDED,
            {"do": "followRefresh"},
            _alive(67, "revalue", None),
            TICK,
            _idle(_run(67, "revalue"), RUN_66),
        ]
    )
    assert other["layer"]["on"] is False and other["inert"] == FREE
    assert other["recomputing"] is True and other["storage"] == {}
    assert ended["reads"] == [SCREEN_URL]
    *_, refused = _trace(
        [
            LANDED,
            {"do": "start", "name": "Refresh prices"},
            {"do": "answer", "url": START_URL, "status": 409, "body": {"running": 67}},
            _alive(67, "price", None),
        ]
    )
    assert refused["notice"] == "A refresh is already running."
    assert refused["layer"]["on"] is False and refused["storage"] == {}


def test_the_layer_draws_the_stage_word_alone_while_the_total_is_0() -> None:
    """As the status line does, where the run bar would draw nothing."""
    begun = _alive(67, "price", None)
    begun["body"]["refresh"] |= {"stage": "quotes", "done": 0, "failed": 0, "remaining": 0}
    *_, locked = _trace([LANDED, *_mine(67, "price"), begun])
    assert locked["layer"]["on"] is True
    assert (locked["layer"]["bar"], locked["layer"]["stage"]) == (False, "fetching prices")


@pytest.mark.parametrize(("kind", "symbols"), [("scoped", ["MSCO"]), ("revalue", ["MGCO"])])
def test_a_run_of_named_companies_draws_no_layer(kind: str, symbols: list[str]) -> None:
    """An agent's run, a moat write's: nothing darkens and nothing locks."""
    *_, alive = _trace([LANDED, TICK, _alive(67, kind, symbols)])
    assert alive["run"] is True
    assert alive["layer"]["on"] is False and alive["layer"]["hidden"] == "true"
    assert alive["inert"] == FREE and alive["closed"] == 0


@pytest.mark.parametrize(("kind", "keep"), [("price", False), ("full", True), ("revalue", True)])
def test_keep_reading_stands_on_the_long_runs_only(kind: str, keep: bool) -> None:
    """A full refresh and a whole revalue run for minutes, and the reader may keep reading; a
    price refresh, about 26 seconds, holds the page to its end."""
    *_, locked = _trace([LANDED, *_mine(67, kind), _alive(67, kind, None)])
    assert locked["layer"]["keep"] is keep
    assert locked["layer"]["sentence"] == (KEPT if keep else LOCKED)


def test_keep_reading_lifts_the_lock_for_that_run_alone() -> None:
    """The run goes on and the page is as under a run today: the bar in the status line, the
    tables faint, Cancel in the header. The next answer about the same run keeps the page free;
    another run the page starts locks it again, with a panel of its own, which takes the focus."""
    trace = _trace(
        [
            LANDED,
            *_mine(67, "full"),
            _alive(67, "full", None),
            KEEP,
            TICK,
            _alive(67, "full", None),
            TICK,
            _idle(_run(67, "full"), RUN_66),
            *_mine(68, "full"),
            _alive(68, "full", None),
        ]
    )
    locked, kept, same, other = trace[3], trace[4], trace[6], trace[-1]
    assert locked["layer"]["on"] is True
    assert kept["layer"]["on"] is False and kept["inert"] == FREE
    assert (kept["run"], kept["recomputing"], kept["actions"]) == (True, True, ["Cancel"])
    assert same["layer"]["on"] is False and same["inert"] == FREE
    assert other["layer"]["on"] is True and other["inert"] == HELD
    assert other["layer"]["title"] == "Refreshing all" and other["focused"] is True


@pytest.mark.parametrize("status", ["done", "failed", "cancelled"])
def test_the_run_s_end_lifts_the_lock(status: str) -> None:
    """A run that ends, done or not, takes the layer away, and the page is free again. The layer
    keeps the panel it last drew, so the scrim and the panel fade out together (4.1), while the
    layer is hidden from a screen reader and inert: nothing in it can be reached."""
    *_, locked, _, ended = _trace(
        [
            LANDED,
            *_mine(67, "price"),
            _alive(67, "price", None),
            TICK,
            _idle(_run(67, "price", status=status)),
        ]
    )
    assert locked["layer"]["on"] is True
    assert ended["layer"]["on"] is False and ended["layer"]["dialog"] is False
    assert (ended["layer"]["hidden"], ended["layer"]["inert"]) == ("true", True)
    assert ended["layer"]["panel"] is True
    assert {key: ended["layer"][key] for key in ("title", "bar", "sentence", "cancel")} == {
        key: locked["layer"][key] for key in ("title", "bar", "sentence", "cancel")
    }
    assert ended["inert"] == FREE and ended["run"] is False and ended["focused"] is False


def test_a_failed_status_read_offers_keep_reading_on_a_price_run() -> None:
    """The plan's review focus 1: the status read fails while the page is locked (the server
    restarts), so the page cannot know whether the run goes on. Keep reading stands on any kind,
    with the notice of the failed read in the panel, so the reader is never held behind the
    layer; a read that answers again with the run alive takes it away from a price run."""
    failed = {"do": "answer", "url": CURRENT, "status": 500, "body": {"detail": "restarting"}}
    *_, locked, _, lost, _, back = _trace(
        [
            LANDED,
            *_mine(67, "price"),
            _alive(67, "price", None),
            TICK,
            failed,
            TICK,
            _alive(67, "price", None),
        ]
    )
    assert locked["layer"]["keep"] is False
    assert lost["layer"]["on"] is True and lost["layer"]["keep"] is True
    assert lost["layer"]["sentence"] == KEPT
    assert lost["layer"]["notice"].startswith("The refresh status did not load: ")
    assert back["layer"]["keep"] is False and back["layer"]["notice"] is None
    *_, kept = _trace([LANDED, *_mine(67, "price"), _alive(67, "price", None), TICK, failed, KEEP])
    assert kept["layer"]["on"] is False and kept["inert"] == FREE


def test_back_and_forward_are_put_back_while_locked() -> None:
    """The plan's review focus 5: a change of the address while the lock holds (Back, Forward, a
    hash typed) is put back to the address the page held as the lock began, and nothing new shows
    or reads. Once the run ends, the address opens its view again."""
    *_, page, _, _, locked, back, forward, _, ended, opened = _trace(
        [
            LANDED,
            _show("company", "MGCO"),
            *_mine(67, "price"),
            _alive(67, "price", None),
            {"do": "hash", "hash": "#statistics"},
            {"do": "hash", "hash": "#company/MGCO/financials"},
            TICK,
            _idle(_run(67, "price"), RUN_66),
            {"do": "hash", "hash": "#statistics"},
        ]
    )
    assert page["hash"] == "#company/MGCO" and locked["layer"]["on"] is True
    for step in (back, forward):
        assert (step["hash"], step["view"], step["reads"]) == ("#company/MGCO", "", [])
        assert step["layer"]["on"] is True
    assert ended["layer"]["on"] is False
    assert (opened["hash"], opened["view"], opened["reads"]) == (
        "#statistics",
        "statistics",
        [STATISTICS],
    )
    *_, screen = _trace(
        [
            LANDED,
            _show("screen"),
            *_mine(67, "full"),
            _alive(67, "full", None),
            {"do": "hash", "hash": "#settings"},
        ]
    )
    assert (screen["hash"], screen["view"], screen["reads"]) == ("", "screen", [])


def test_the_list_picked_is_the_address_put_back() -> None:
    """The watchlist page writes its list's address itself, #watchlists/<id>, as the reader picks
    a list in its head (watchlists.js), not through FairbandPage.show. The address put back while
    locked is the one the page held as the lock began, so it names the list shown."""
    *_, picked, _, _, locked, back = _trace(
        [
            LANDED,
            _show("watchlists"),
            {"do": "list", "id": 5},
            *_mine(67, "price"),
            _alive(67, "price", None),
            {"do": "hash", "hash": ""},
        ]
    )
    assert (picked["hash"], picked["view"]) == ("#watchlists/5", "watchlists")
    assert locked["layer"]["on"] is True
    assert (back["hash"], back["view"], back["reads"]) == ("#watchlists/5", "watchlists", [])


def test_escape_does_nothing_while_locked() -> None:
    """Escape does not close the layer, and nothing under it answers: its default is prevented,
    so the drawer, whose Escape gives way to one acted on, stays open (app.js). Free, the page's
    Escape is its own again."""
    *_, free, _, _, locked, escaped = _trace(
        [LANDED, ESCAPE, *_mine(67, "price"), _alive(67, "price", None), ESCAPE]
    )
    assert free["prevented"] is False
    assert locked["layer"]["on"] is True
    assert escaped["prevented"] is True and escaped["layer"]["on"] is True


def test_the_layer_s_mount_and_rules_stand() -> None:
    """The layer's mount is the body's child after main.app-page, so it covers the header too;
    its scrim has a value in each theme and in the light preference, as tokens.css declares its
    themes, and it fades in and out over 150 ms, the one motion of the layer (4.8)."""
    page = " ".join(_static_file("index.html").split())
    assert '</main> <div id="layer"></div> <script ' in page
    assert ':root, [data-theme="dark"] { --app-scrim: rgb(0 0 0 / 0.62); }' in page
    assert '[data-theme="light"] { --app-scrim: rgb(17 22 27 / 0.5); }' in page
    assert (
        "@media (prefers-color-scheme: light) { :root:not([data-theme]) "
        "{ --app-scrim: rgb(17 22 27 / 0.5); } }"
    ) in page
    assert "transition: opacity 150ms, visibility 0s 150ms; }" in page
    assert (
        ".app-layer.is-on { opacity: 1; visibility: visible; transition: opacity 150ms; }" in page
    )


def test_cancel_in_the_layer_asks_the_server_and_is_disabled_after() -> None:
    """Cancel does what the header's Cancel does: it posts, and once the server takes it, it is
    disabled until the run ends, the notice in the panel; the state is read at once."""
    *_, locked, pressed, taken = _trace(
        [
            LANDED,
            *_mine(67, "full"),
            _alive(67, "full", None),
            CANCEL,
            {"do": "answer", "url": CANCEL_URL, "status": 200, "body": {"cancelled": True}},
        ]
    )
    assert locked["layer"]["cancel"] == "enabled"
    assert pressed["reads"] == [CANCEL_URL] and pressed["layer"]["cancel"] == "enabled"
    assert taken["reads"] == [CURRENT]
    assert taken["layer"]["cancel"] == "disabled" and taken["layer"]["keep"] is True
    assert taken["layer"]["notice"] == (
        "Cancel asked: the refresh stops after the companies in flight."
    )
