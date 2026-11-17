"""The company page's loader as it runs (the company page's design, 7.1 and 7.5): the real app.js,
controls.js and company.js in node (``tests/web/company_load.mjs``), with a fetch that answers only
when a step answers it, so each test says when each read lands. Each test reads, after each step,
what was fetched, what is still in flight, the companies handed ``FairbandPage.notesShown``, the
popups drawn and what the page draws: faded or not, a failed read's sentence, the head's ticker
and price, the tab selected and what the open tab's function was handed (the driver's own
function draws the mark of the tab's answer and the price of the detail).

The transitions: a tab held, shown with no read; a tab whose read is out, asked for again; a
refresh that ends during a tab's read; a tab held, asked for while a read of the detail is out;
another company, whose first company's late landing is dropped; a failed read of the detail and
of a tab; a read that lands after the reader left the view; and the popups, which close as a view
is shown."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support import page_answers as answers
from support.page import BUNDLE, NODE, STATIC

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

DRIVER = Path(__file__).parent / "company_load.mjs"
SCRIPTS = (
    BUNDLE,
    STATIC / "app.js",
    STATIC / "finder.js",
    STATIC / "controls.js",
    STATIC / "company.js",
)
LFOX = "/api/companies/LFOX"
OVERVIEW = LFOX + "/page/overview"
ESTIMATES = LFOX + "/page/estimates"
FINANCIALS = LFOX + "/page/financials"
RESEARCH = LFOX + "/page/research"
NOTES = LFOX + "/notes"
BRK = "/api/companies/BRK.B"
RETRY = "The company's data did not load: {}. Open the page again to retry."


def _drive(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The trace of ``steps``: one entry for each, as ``company_load.mjs`` gives it."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(DRIVER), *(str(script) for script in SCRIPTS)],
        input=json.dumps(steps),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    trace: list[dict[str, Any]] = json.loads(done.stdout)
    return trace


def _detail(price: float, symbol: str = "LFOX") -> dict[str, Any]:
    """The company's detail as ``GET /api/companies/{symbol}`` answers it, at ``price``."""
    found = answers.detail()
    found["result"] |= {"symbol": symbol, "price": price}
    found["company"] |= {"symbol": symbol}
    return found


def _tab(mark: str, symbol: str = "LFOX") -> dict[str, Any]:
    """A tab's answer, named by its mark: the head reads its quote and its data date, and the
    Overview's its news, which are not stale, so no second read follows."""
    return {
        "symbol": symbol,
        "mark": mark,
        "dataDate": "2026-11-14",
        "quote": None,
        "news": {"stories": [], "stale": False, "limit": 60},
    }


def _show(symbol: str, tab: str, report: int | None = None) -> dict[str, Any]:
    return {"do": "show", "symbol": symbol, "tab": tab, "id": report}


def _answer(url: str, body: Any, status: int = 200) -> dict[str, Any]:
    return {"do": "answer", "url": url, "status": status, "body": body}


def _fail(url: str, message: str = "Failed to fetch") -> dict[str, Any]:
    return {"do": "fail", "url": url, "message": message}


def _drawn(tab: str, mark: str, price: float) -> dict[str, Any]:
    """What the open tab's function was handed: its answer's mark and the detail's price."""
    return {"tab": tab, "mark": mark, "price": price}


def _get(*urls: str) -> list[list[str]]:
    return [["GET", url] for url in urls]


AGAIN = {"do": "again"}  # a refresh's end, or a note taken in the head: the loader runs again
LEFT = {"do": "hash", "hash": "#"}  # the browser's Back, to the screen
# The page opened on LFOX's Overview, both reads landed: the detail at $182.40, then the tab.
OPEN = [
    _show("LFOX", "overview"),
    _answer(LFOX, _detail(182.4)),
    _answer(OVERVIEW, _tab("overview 1")),
]
OPENED = {
    "faded": False,
    "sentence": None,
    "ticker": "LFOX",
    "price": "$182.40",
    "tab": "Overview",
    "drawn": _drawn("overview", "overview 1", 182.4),
}


def test_the_page_opens_on_the_detail_then_the_tab() -> None:
    """The detail is read first, the page faded with the hash's ticker; then the tab's read; the
    page draws both once the tab lands. It turns to the company as it is asked for it and again
    as the read lands: notesShown with it at each."""
    shown, detail, tab = _drive(OPEN)
    assert shown["fetched"] == _get(LFOX)
    assert shown["notesShown"] == ["LFOX"]
    assert shown["hash"] == "#company/LFOX" and shown["shows"] is True
    assert shown["page"] == {
        "faded": True,
        "sentence": None,
        "ticker": "LFOX",
        "price": None,
        "tab": None,
        "drawn": None,
    }
    assert detail["fetched"] == _get(OVERVIEW)
    assert detail["page"]["faded"] is True and detail["page"]["drawn"] is None
    assert tab["fetched"] == [] and tab["inFlight"] == []
    assert tab["page"] == OPENED
    assert detail["notesShown"] == []
    assert tab["notesShown"] == ["LFOX"]


def test_a_tab_held_is_shown_at_once_with_no_read() -> None:
    """Another tab of the company reads that tab alone, the detail kept; a tab the page holds is
    shown at once, with no read."""
    trace = _drive(
        OPEN
        + [
            _show("LFOX", "estimates"),
            _answer(ESTIMATES, _tab("estimates 1")),
            _show("LFOX", "overview"),
            _show("LFOX", "estimates"),
        ]
    )
    other, landed, overview, estimates = trace[3:]
    assert other["fetched"] == _get(ESTIMATES)
    assert other["page"] == OPENED | {"faded": True}
    assert landed["page"] == OPENED | {
        "tab": "Estimates",
        "drawn": _drawn("estimates", "estimates 1", 182.4),
    }
    for held in (overview, estimates):
        assert held["fetched"] == [] and held["inFlight"] == []
        assert held["notesShown"] == []
    assert overview["page"] == OPENED
    assert overview["hash"] == "#company/LFOX"
    assert estimates["page"] == landed["page"]
    assert estimates["hash"] == "#company/LFOX/estimates"


def test_the_financials_tab_is_read_where_its_hash_names_it() -> None:
    """#company/LFOX/financials (a link, the browser's Back) opens the Financials tab: the detail,
    then /page/financials, drawn by the tab's function; once held, the tab's button shows it again
    with no read, and the hash names it."""
    trace = _drive(
        [
            {"do": "hash", "hash": "#company/LFOX/financials"},
            _answer(LFOX, _detail(182.4)),
            _answer(FINANCIALS, _tab("financials 1")),
            _show("LFOX", "estimates"),
            _answer(ESTIMATES, _tab("estimates 1")),
            _show("LFOX", "financials"),
        ]
    )
    hashed, detail, landed, estimates, _, again = trace
    assert hashed["fetched"] == _get(LFOX)
    assert hashed["shows"] is True
    assert detail["fetched"] == _get(FINANCIALS)
    shown = OPENED | {"tab": "Financials", "drawn": _drawn("financials", "financials 1", 182.4)}
    assert landed["page"] == shown
    assert landed["hash"] == "#company/LFOX/financials"
    assert estimates["fetched"] == _get(ESTIMATES)
    assert again["fetched"] == [] and again["inFlight"] == []
    assert again["page"] == shown
    assert again["hash"] == "#company/LFOX/financials"


def test_research_is_a_tab_that_reads_the_report_its_address_names() -> None:
    """Research is the fourth tab (the Research tab's design, 7.1): ``show('company', 'AAPL',
    'research', 12)`` names the report in the hash, #company/AAPL/research/12, and reads the tab
    with its id, ?report=12; the tab without an id is the company's latest report, read with no
    query, the detail kept."""
    aapl = "/api/companies/AAPL"
    trace = _drive(
        [
            _show("AAPL", "research", 12),
            _answer(aapl, _detail(182.4, "AAPL")),
            _answer(aapl + "/page/research?report=12", _tab("report 12", "AAPL")),
            _show("AAPL", "research"),
            _answer(aapl + "/page/research", _tab("the latest report", "AAPL")),
        ]
    )
    shown, detail, landed, latest, again = trace
    assert shown["hash"] == "#company/AAPL/research/12"
    assert shown["fetched"] == _get(aapl)
    assert detail["fetched"] == _get(aapl + "/page/research?report=12")
    shown_page = OPENED | {"ticker": "AAPL", "tab": "Research"}
    assert landed["page"] == shown_page | {"drawn": _drawn("research", "report 12", 182.4)}
    assert latest["hash"] == "#company/AAPL/research"
    assert latest["fetched"] == _get(aapl + "/page/research")
    assert again["page"] == shown_page | {"drawn": _drawn("research", "the latest report", 182.4)}


def test_an_id_that_is_not_a_whole_number_names_no_report() -> None:
    """#company/LFOX/research/x keeps no id: the hash is written back without it and the tab
    reads the latest report."""
    hashed, detail = _drive(
        [{"do": "hash", "hash": "#company/LFOX/research/x"}, _answer(LFOX, _detail(182.4))]
    )
    assert hashed["hash"] == "#company/LFOX/research"
    assert detail["fetched"] == _get(RESEARCH)


def test_a_report_s_old_address_opens_the_research_tab_on_the_same_report() -> None:
    """#report/<symbol> and #report/<symbol>/<id>, the addresses of the report page, which left
    (the Research tab's design, 7.1 and 9), open the company page's Research tab on the same
    report, a link or a bookmark of the old form still opening the report, and the hash is
    replaced by the tab's: the company's latest report, read with no query, or the report with
    that id; the symbol upper-cased as the store keeps it. #report with no symbol is the Screen,
    as it was."""
    aapl = "/api/companies/AAPL"
    latest, detail, landed = _drive(
        [
            {"do": "hash", "hash": "#report/AAPL"},
            _answer(aapl, _detail(182.4, "AAPL")),
            _answer(aapl + "/page/research", _tab("the latest report", "AAPL")),
        ]
    )
    assert latest["hash"] == "#company/AAPL/research" and latest["shows"] is True
    assert latest["fetched"] == _get(aapl)
    assert detail["fetched"] == _get(aapl + "/page/research")
    assert landed["page"] == OPENED | {
        "ticker": "AAPL",
        "tab": "Research",
        "drawn": _drawn("research", "the latest report", 182.4),
    }
    revision, detail = _drive(
        [{"do": "hash", "hash": "#report/aapl/9"}, _answer(aapl, _detail(182.4, "AAPL"))]
    )
    assert revision["hash"] == "#company/AAPL/research/9" and revision["shows"] is True
    assert detail["fetched"] == _get(aapl + "/page/research?report=9")
    screen = _drive(OPEN + [{"do": "hash", "hash": "#report"}])[-1]
    assert screen["hash"] == "" and screen["shows"] is False and screen["fetched"] == []


def test_open_report_opens_the_research_tab_on_the_report() -> None:
    """``FairbandPage.openReport(symbol, id)`` opens the tab as the old address does: on the
    report with that id, or on the company's latest report where none is given."""
    aapl = "/api/companies/AAPL"
    opened, detail = _drive(
        [{"do": "openReport", "symbol": "AAPL", "id": 9}, _answer(aapl, _detail(182.4, "AAPL"))]
    )
    assert opened["hash"] == "#company/AAPL/research/9" and opened["shows"] is True
    assert opened["fetched"] == _get(aapl)
    assert detail["fetched"] == _get(aapl + "/page/research?report=9")
    [latest] = _drive([{"do": "openReport", "symbol": "AAPL", "id": None}])
    assert latest["hash"] == "#company/AAPL/research"


def test_another_report_of_the_tab_shown_drops_the_first_s_late_answer() -> None:
    """Another id of the tab reads the tab again, the detail kept; the answer of the report asked
    for first, landing after the second was asked for, is dropped, and the page stays faded on
    what it showed until the second lands. A report read before is held by its id: shown again at
    once, with no read."""
    trace = _drive(
        OPEN
        + [
            _show("LFOX", "research", 31),
            _show("LFOX", "research", 19),
            _answer(RESEARCH + "?report=31", _tab("report 31")),
            _answer(RESEARCH + "?report=19", _tab("report 19")),
            _show("LFOX", "overview"),
            _show("LFOX", "research", 19),
            _show("LFOX", "research", 31),
        ]
    )
    first, second, late, landed, overview, held, dropped = trace[3:]
    assert first["fetched"] == _get(RESEARCH + "?report=31")
    assert second["fetched"] == _get(RESEARCH + "?report=19")
    assert second["hash"] == "#company/LFOX/research/19"
    assert late["page"] == OPENED | {"faded": True}
    shown = OPENED | {"tab": "Research", "drawn": _drawn("research", "report 19", 182.4)}
    assert landed["page"] == shown
    assert overview["page"] == OPENED and overview["fetched"] == []
    assert held["fetched"] == [] and held["page"] == shown
    assert dropped["fetched"] == _get(RESEARCH + "?report=31")


def test_a_404_of_the_research_read_is_the_server_s_sentence() -> None:
    """An id of another company's report, or of none, or a company with no page data: the
    tab's 404 draws the server's sentence under the tabs as it arrives, since opening the page
    again would not help; any other failure of the read, the page's sentence."""
    trace = _drive(
        [
            _show("LFOX", "research", 9),
            _answer(LFOX, _detail(182.4)),
            _answer(RESEARCH + "?report=9", {"detail": "report 9 is NVDA's, not LFOX's"}, 404),
            _show("LFOX", "research", 7),
            _answer(RESEARCH + "?report=7", {"detail": "no report 7"}, 404),
            _show("LFOX", "research"),
            _answer(RESEARCH, {"detail": "no page data for LFOX"}, 404),
            _show("LFOX", "research", 8),
            _answer(RESEARCH + "?report=8", None, 500),
            _show("LFOX", "research", 6),
            _fail(RESEARCH + "?report=6"),
        ]
    )
    failed = OPENED | {"tab": "Research", "drawn": None}
    assert trace[2]["page"] == failed | {"sentence": "report 9 is NVDA's, not LFOX's"}
    assert trace[4]["page"] == failed | {"sentence": "no report 7"}
    assert trace[6]["page"] == failed | {"sentence": "no page data for LFOX"}
    assert trace[8]["page"] == failed | {"sentence": RETRY.format("the server answered 500")}
    assert trace[10]["page"] == failed | {"sentence": RETRY.format("Failed to fetch")}


def test_a_tab_whose_read_is_out_asked_for_again_is_read_whole() -> None:
    """The tab whose read is out, not yet shown, asked for again (a note taken in the head, a
    refresh's end) reads the detail and the tab; the first read lands late and is dropped; the
    whole read drops what the page held of the other tab, which is read again when shown."""
    trace = _drive(
        OPEN
        + [
            _show("LFOX", "estimates"),
            AGAIN,
            _answer(ESTIMATES, _tab("estimates, the first read")),
            _answer(LFOX, _detail(182.4)),
            _answer(ESTIMATES, _tab("estimates 2")),
            _show("LFOX", "overview"),
        ]
    )
    out, again, late, detail, landed, overview = trace[3:]
    assert out["fetched"] == _get(ESTIMATES)
    assert again["fetched"] == _get(LFOX)
    assert again["inFlight"] == [ESTIMATES, LFOX]
    assert late["page"] == OPENED | {"faded": True}
    assert detail["fetched"] == _get(ESTIMATES)
    assert landed["page"]["drawn"] == _drawn("estimates", "estimates 2", 182.4)
    assert landed["page"]["faded"] is False
    assert overview["fetched"] == _get(OVERVIEW)


def test_a_refresh_that_ends_during_a_tab_s_read_reads_the_detail_too() -> None:
    """A run ends while the reader's tab loads: the page reads the detail and the tab, so the head
    and the tab draw the run's figures, and the other tab, held from before the run, is read
    again when shown, never drawn with the figures of before it."""
    trace = _drive(
        OPEN
        + [
            _show("LFOX", "estimates"),
            AGAIN,
            _answer(LFOX, _detail(190.0)),
            _answer(ESTIMATES, _tab("estimates, before the run")),
            _answer(ESTIMATES, _tab("estimates, after the run")),
            _show("LFOX", "overview"),
            _answer(OVERVIEW, _tab("overview, after the run")),
        ]
    )
    ended, detail, late, landed, overview, again = trace[4:]
    assert ended["fetched"] == _get(LFOX)
    assert detail["fetched"] == _get(ESTIMATES)
    assert late["page"] == OPENED | {"faded": True}
    assert landed["page"] == OPENED | {
        "price": "$190.00",
        "tab": "Estimates",
        "drawn": _drawn("estimates", "estimates, after the run", 190.0),
    }
    assert overview["fetched"] == _get(OVERVIEW)
    assert overview["page"]["faded"] is True
    assert again["page"]["drawn"] == _drawn("overview", "overview, after the run", 190.0)


def test_a_tab_held_asked_for_while_the_detail_is_read_is_read_whole() -> None:
    """While a read of the detail is out (a refresh's end), a tab the page holds from before it is
    not shown at once: the page reads the detail and that tab, so the reread is never dropped for
    the figures of before the run."""
    trace = _drive(
        OPEN
        + [
            _show("LFOX", "estimates"),
            _answer(ESTIMATES, _tab("estimates 1")),
            _show("LFOX", "overview"),
            AGAIN,
            _show("LFOX", "estimates"),
            _answer(LFOX, _detail(190.0)),
            _answer(LFOX, _detail(190.0)),
            _answer(OVERVIEW, _tab("overview, after the run")),
            _answer(ESTIMATES, _tab("estimates, after the run")),
        ]
    )
    again, held = trace[6:8]
    assert again["fetched"] == _get(LFOX)
    assert held["fetched"] == _get(LFOX)
    assert held["page"]["faded"] is True
    assert held["page"]["drawn"] == _drawn("overview", "overview 1", 182.4)
    first, second, dropped, landed = trace[8:]
    assert first["fetched"] == _get(OVERVIEW)  # the first whole read goes on, to be dropped
    assert second["fetched"] == _get(ESTIMATES)
    assert dropped["page"]["drawn"] == _drawn("overview", "overview 1", 182.4)
    assert landed["page"] == OPENED | {
        "price": "$190.00",
        "tab": "Estimates",
        "drawn": _drawn("estimates", "estimates, after the run", 190.0),
    }


def test_another_company_drops_the_first_company_s_late_landing() -> None:
    """The page turns to another company as it is asked for one: notesShown with it at the turn.
    A read of the first company that lands after the turn is dropped and hands notesShown
    nothing. The new company's landing turns the page, notesShown with it again (a Notes box
    opened from the faded head while the read was out closes), and draws its head and its tab."""
    trace = _drive(
        OPEN
        + [
            AGAIN,
            _show("BRK.B", "overview"),
            _answer(LFOX, _detail(182.4)),
            _answer(OVERVIEW, _tab("overview, the first company's")),
            _answer(BRK, _detail(501.25, "BRK.B")),
            _answer(BRK + "/page/overview", _tab("overview of BRK.B", "BRK.B")),
        ]
    )
    again, turned, late, dropped, detail, landed = trace[3:]
    assert again["fetched"] == _get(LFOX) and again["notesShown"] == []
    assert turned["fetched"] == _get(BRK)
    assert turned["notesShown"] == ["BRK.B"]
    assert turned["hash"] == "#company/BRK.B"
    assert turned["page"] == OPENED | {"faded": True}
    assert late["fetched"] == _get(OVERVIEW)
    for step in (late, dropped):
        assert step["notesShown"] == []
        assert step["page"] == OPENED | {"faded": True}
    assert detail["fetched"] == _get(BRK + "/page/overview")
    assert landed["notesShown"] == ["BRK.B"]
    assert landed["page"] == {
        "faded": False,
        "sentence": None,
        "ticker": "BRK.B",
        "price": "$501.25",
        "tab": "Overview",
        "drawn": _drawn("overview", "overview of BRK.B", 501.25),
    }


def test_a_failed_read_of_the_detail_draws_its_sentence_in_the_head_s_place() -> None:
    """A detail read that fails draws the Words table's sentence, which says to open the page
    again, and no head; a 404, a company with no snapshot, the server's own sentence. Opened
    again, the page reads anew and draws the company once both reads land."""
    trace = _drive(
        [
            _show("LFOX", "overview"),
            _fail(LFOX),
            AGAIN,
            _answer(LFOX, None, 500),
            AGAIN,
            _answer(LFOX, {"detail": "no snapshot for LFOX"}, 404),
            AGAIN,
            _answer(LFOX, _detail(182.4)),
            _answer(OVERVIEW, _tab("overview 1")),
        ]
    )
    failed = {"faded": False, "ticker": None, "price": None, "tab": None, "drawn": None}
    assert trace[1]["page"] == failed | {"sentence": RETRY.format("Failed to fetch")}
    assert trace[1]["inFlight"] == []
    assert trace[2]["fetched"] == _get(LFOX)
    assert trace[2]["page"] == failed | {
        "faded": True,
        "sentence": RETRY.format("Failed to fetch"),
    }
    assert trace[3]["page"] == failed | {"sentence": RETRY.format("the server answered 500")}
    assert trace[5]["page"] == failed | {"sentence": "no snapshot for LFOX"}
    assert trace[8]["page"] == OPENED


def test_a_failed_read_of_a_tab_draws_its_sentence_under_the_tabs() -> None:
    """A tab's read that fails draws the head and the tabs and, under them, the Words table's
    sentence with the server's message, its 404 among them, or the browser's."""
    trace = _drive(
        [
            _show("LFOX", "overview"),
            _answer(LFOX, _detail(182.4)),
            _answer(OVERVIEW, {"detail": "no page data for LFOX"}, 404),
            _show("LFOX", "estimates"),
            _fail(ESTIMATES),
        ]
    )
    assert trace[2]["page"] == OPENED | {
        "sentence": RETRY.format("no page data for LFOX"),
        "drawn": None,
    }
    assert trace[3]["fetched"] == _get(ESTIMATES)
    assert trace[4]["page"] == OPENED | {
        "sentence": RETRY.format("Failed to fetch"),
        "tab": "Estimates",
        "drawn": None,
    }


def test_a_read_that_lands_after_the_reader_left_the_view_leaves_the_notes_alone() -> None:
    """The reader turned the page to another company, then left the view before its read landed
    (the browser's Back, to the screen, where the drawer's Notes box may be open on a third
    company): the landing, or the failure, hands notesShown nothing, so it closes no box and
    drops no draft of another view's. The page holds what landed for the reader's return."""
    for outcome in (
        [
            _answer(BRK, _detail(501.25, "BRK.B")),
            _answer(BRK + "/page/overview", _tab("overview of BRK.B", "BRK.B")),
        ],
        [_fail(BRK)],
    ):
        trace = _drive(OPEN + [_show("BRK.B", "overview"), LEFT, *outcome])
        turned, left, *landing = trace[3:]
        assert turned["notesShown"] == ["BRK.B"]
        assert left["shows"] is False and left["hash"] == ""
        for step in landing:
            assert step["notesShown"] == []
            assert step["shows"] is False
    held = _drive(
        OPEN
        + [
            _show("BRK.B", "overview"),
            LEFT,
            _answer(BRK, _detail(501.25, "BRK.B")),
            _answer(BRK + "/page/overview", _tab("overview of BRK.B", "BRK.B")),
        ]
    )[-1]
    assert held["page"]["ticker"] == "BRK.B"
    assert held["page"]["drawn"] == _drawn("overview", "overview of BRK.B", 501.25)


def test_the_popups_close_as_a_view_is_shown() -> None:
    """A Notes box or a watchlists popup opened from the page's head closes as a view is shown:
    the browser's Back to the screen, its Forward back to the page, a tab's button."""
    trace = _drive(
        OPEN
        + [
            {"do": "notes"},
            LEFT,
            {"do": "hash", "hash": "#company/LFOX"},
            _answer(LFOX, _detail(182.4)),
            _answer(OVERVIEW, _tab("overview 1")),
            {"do": "watch"},
            LEFT,
            {"do": "hash", "hash": "#company/LFOX"},
            {"do": "notes"},
            _show("LFOX", "estimates"),
            {"do": "watch"},
            _show("LFOX", "overview"),
        ]
    )
    notes, back, forward = trace[3:6]
    assert notes["fetched"] == _get(NOTES)
    assert notes["popups"] == ["NotesBox"]
    assert back["shows"] is False and back["popups"] == []
    assert forward["shows"] is True and forward["popups"] == []
    assert forward["fetched"] == _get(LFOX)
    watch, back, forward = trace[8:11]
    assert watch["popups"] == ["WatchMenu"]
    assert back["popups"] == [] and forward["popups"] == []
    notes, tab, watch, other = trace[11:]
    assert notes["popups"] == ["NotesBox"]
    assert tab["popups"] == []
    assert watch["popups"] == ["WatchMenu"]
    assert other["popups"] == []


def test_another_company_opens_at_its_head_and_the_same_company_keeps_the_readers_place() -> None:
    """The panel scrolls, and it stays shown from one company to the next, so the page of a
    company picked in the header's finder would open at the depth the reader left: the loader
    takes the panel back to its top as it turns to another company. A reread at a refresh's end
    and a tab of the same company keep the reader's place."""
    trace = _drive(
        [
            *OPEN,
            {"do": "scroll", "top": 900},
            AGAIN,
            _show("LFOX", "estimates"),
            _show("BRK.B", "overview"),
        ]
    )
    assert [step["scrollTop"] for step in trace[3:]] == [900, 900, 900, 0]
