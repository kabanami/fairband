"""The company page's loader as it runs (the company page's design, 7.1 and 7.5): the real app.js,
controls.js, company.js and company_investor.js in node (``tests/web/company_load.mjs``), with a
fetch that answers only when a step answers it, so each test says when each read lands. Each test
reads, after each step, what was fetched and the headers it carried, what is still in flight, the
companies handed ``FairbandPage.notesShown``, the popups drawn and what the page draws: faded or
not, a failed read's sentence, the head's ticker and price, the tab selected and what the open
tab's function was handed (the driver's own function draws the mark of the tab's answer and the
price of the detail, and on the Investor relations tab the address's word), the data date at the
row's right end and the view the Investor relations tab's switch selects.

The transitions: a tab held, shown with no read; a tab whose read is out, asked for again; a
refresh that ends during a tab's read; a tab held, asked for while a read of the detail is out;
another company, whose first company's late landing is dropped; a failed read of the detail and
of a tab; a read that lands after the reader left the view; the popups, which close as a view is
shown; the panel's place, back at its top as the company or the Research tab's report changes;
and the Investor relations tab's addresses, whose word after the tab's name (a call, ``2026Q4``,
or ``filings``) never travels to the server, so a change of it, by the address or the tab's
switch, draws the answer held again and never reads the tab again, even while the tab's own read
is out, the Earnings calls view's one read its call's transcript, once a call; a call the company
has none of put right to the tab alone, the row's date counting the transcript shown, and the
page back at its top as the call changes (the Investor relations tab's design, 7.1, 7.4 and
7.6)."""

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
    STATIC / "company_investor.js",
)
LFOX = "/api/companies/LFOX"
OVERVIEW = LFOX + "/page/overview"
ESTIMATES = LFOX + "/page/estimates"
FINANCIALS = LFOX + "/page/financials"
RESEARCH = LFOX + "/page/research"
INVESTOR = LFOX + "/page/investor-relations"
IR = "#company/LFOX/investor-relations"
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


def _show(symbol: str, tab: str, report: int | str | None = None) -> dict[str, Any]:
    """A link or a tab's button opens the page at ``tab``, at the id ``report``: a report's on
    the Research tab, a call or ``filings`` on the Investor relations tab."""
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


def test_a_tab_whose_function_throws_as_its_read_lands_draws_the_failure_sentence() -> None:
    """A tab's function that throws as its answer lands, a fault in its script, ends the read as
    one that failed: the page draws the Words table's sentence with the error's message, no
    longer faded, and no error escapes the loader. The page keeps the address asked for: opened
    again, it reads that tab, and the Investor relations tab's word, whole, and draws them."""
    fault = "the tab's function failed"
    trace = _drive(
        OPEN
        + [
            _show("LFOX", "estimates"),
            _answer(ESTIMATES, _tab("estimates 1") | {"throws": fault}),
            AGAIN,
            _answer(LFOX, _detail(182.4)),
            _answer(ESTIMATES, _tab("estimates 2")),
        ]
    )
    failed, again, detail, landed = trace[4:]
    assert failed["page"] == {
        "faded": False,
        "sentence": RETRY.format(fault),
        "ticker": None,
        "price": None,
        "tab": None,
        "drawn": None,
    }
    assert failed["hash"] == "#company/LFOX/estimates" and failed["inFlight"] == []
    assert again["fetched"] == _get(LFOX)
    assert detail["fetched"] == _get(ESTIMATES)
    assert landed["page"] == OPENED | {
        "tab": "Estimates",
        "drawn": _drawn("estimates", "estimates 2", 182.4),
    }

    trace = _drive(
        OPEN
        + [
            {"do": "hash", "hash": "#company/LFOX/investor-relations/filings"},
            _answer(LFOX + "/page/investor-relations", answers.investor() | {"throws": fault}),
            AGAIN,
            _answer(LFOX, _detail(182.4)),
            _answer(LFOX + "/page/investor-relations", answers.investor() | {"mark": "ir 2"}),
        ]
    )
    failed, again, detail, landed = trace[4:]
    assert failed["page"]["sentence"] == RETRY.format(fault)
    assert failed["page"]["faded"] is False
    assert failed["hash"] == "#company/LFOX/investor-relations/filings"
    assert again["fetched"] == _get(LFOX)
    assert detail["fetched"] == _get(LFOX + "/page/investor-relations")
    assert landed["page"]["drawn"] == {
        "tab": "investor-relations",
        "mark": "ir 2",
        "price": 182.4,
        "id": "filings",
    }
    assert landed["view"] == "Filings"


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


def test_another_report_opens_at_its_head_and_the_same_report_keeps_the_readers_place() -> None:
    """The Research tab's design, 7.3: the section list stays in view while the report scrolls,
    so a press on another report under Reports on file, deep in the page, would open it at the
    depth the reader left: the loader takes the panel back to its top as the report the Research
    tab shows changes, to another id or from an id to the latest, whether that report is read or
    held. The same report's answer landing again (a refresh's end, a note taken), another tab and
    the same report on coming back keep the reader's place."""
    trace = _drive(
        [
            _show("LFOX", "research", 31),
            _answer(LFOX, _detail(182.4)),
            _answer(RESEARCH + "?report=31", _tab("report 31")),
            {"do": "scroll", "top": 900},
            AGAIN,
            _answer(LFOX, _detail(182.4)),
            _answer(RESEARCH + "?report=31", _tab("report 31, again")),
            _show("LFOX", "overview"),
            _answer(OVERVIEW, _tab("overview 1")),
            _show("LFOX", "research", 31),
            _show("LFOX", "research", 19),
            _answer(RESEARCH + "?report=19", _tab("report 19")),
            {"do": "scroll", "top": 700},
            _show("LFOX", "research", 31),
            {"do": "scroll", "top": 600},
            _show("LFOX", "overview"),
            _show("LFOX", "research", 19),
            {"do": "scroll", "top": 500},
            _show("LFOX", "research"),
            _answer(RESEARCH, _tab("the latest report")),
        ]
    )
    held = trace[9]
    assert held["fetched"] == []
    assert held["page"]["drawn"] == _drawn("research", "report 31, again", 182.4)
    assert trace[13]["fetched"] == [] and trace[16]["fetched"] == []  # held: shown at once
    assert [step["scrollTop"] for step in trace[3:]] == [
        900,  # scrolled down report 31
        900,  # a refresh's end reads the same report again
        900,
        900,  # its answer lands again
        900,  # another tab
        900,
        900,  # back to the same report
        0,  # another report
        0,
        700,
        0,  # another report, held
        600,
        600,  # another tab
        0,  # back to the tab on another report than it showed last
        500,
        0,  # from an id to the latest
        0,
    ]


# --------------------------------------------------------------- the Investor relations tab


def _investor(mark: str, **changes: Any) -> dict[str, Any]:
    """The Investor relations tab's answer (``page_answers``' LFOX: its data date 14 Nov 2026,
    its filing list's day 2 Nov 2026), named by its mark, with ``changes``."""
    return answers.investor() | {"mark": mark} | changes


def _hash(word: str | None = None) -> dict[str, Any]:
    """A link, or the browser, moves the hash to the Investor relations tab, at ``word``."""
    return {"do": "hash", "hash": IR + ("" if word is None else "/" + word)}


def _switch(view: str) -> dict[str, Any]:
    """The Investor relations tab's switch pressed on its button named ``view``."""
    return {"do": "switch", "view": view}


def _ir(mark: str, word: str | None, price: float = 182.4) -> dict[str, Any]:
    """What the Investor relations tab's function was handed: its answer's mark, the detail's
    price and the address's word."""
    return _drawn("investor-relations", mark, price) | {"id": word}


IR_OPENED = OPENED | {"tab": "Investor relations"}
ON_CALLS = "data 14 Nov 2026"  # the read's data date, the Earnings calls view's
ON_FILINGS = "data 2 Nov 2026"  # the filing list's day, the Filings view's
# The Earnings calls view's read of a call's transcript, with the request header: LFOX's newest
# call, Q3 2026, and its others.
CALL = INVESTOR + "/call?year={}&quarter={}"
CALL_Q3 = CALL.format(2026, 3)
CALL_Q2 = CALL.format(2026, 2)
HEADER = {"X-Fairband-Request": "1"}


def _call(year: int = 2026, quarter: int = 3, observed: str = "2026-11-15") -> dict[str, Any]:
    """The call's read's answer: one turn of words, its copy fetched on ``observed``."""
    return {
        "symbol": "LFOX",
        "fiscalYear": year,
        "quarter": quarter,
        "date": "2026-10-15",
        "turns": [{"speaker": "Operator", "paragraphs": ["Good afternoon."]}],
        "questionsAt": None,
        "observedDay": observed,
    }


@pytest.mark.parametrize(
    ("word", "kept", "call"),
    [
        (None, None, CALL_Q3),
        ("2026Q2", "2026Q2", CALL_Q2),
        ("filings", "filings", None),
        ("2026Q5", None, CALL_Q3),
        ("nonsense", None, CALL_Q3),
        ("12", None, CALL_Q3),
        ("2026q4", None, CALL_Q3),
        ("Filings", None, CALL_Q3),
    ],
)
def test_the_tab_s_addresses(word: str | None, kept: str | None, call: str | None) -> None:
    """#company/LFOX/investor-relations, /2026Q2 (a call: a fiscal year and Q1 to Q4) and
    /filings are kept and written back; any other word (a fifth quarter, a word, a report's id)
    is put right to the tab alone (7.1). Each reads the detail, then the tab's own read with no
    query and no header, the word never travelling to the server, and the tab's function is
    handed the word kept; the view and the data date follow it. As it lands, the Earnings calls
    view reads its call's transcript, the newest on the tab alone, with the request header."""
    hashed, detail, landed = _drive(
        [_hash(word), _answer(LFOX, _detail(182.4)), _answer(INVESTOR, _investor("ir 1"))]
    )
    written = IR + ("" if kept is None else "/" + kept)
    assert hashed["hash"] == written and hashed["shows"] is True
    assert hashed["fetched"] == _get(LFOX)
    assert detail["fetched"] == _get(INVESTOR)
    assert detail["headers"] == [None]
    assert landed["hash"] == written
    assert landed["page"] == IR_OPENED | {"drawn": _ir("ir 1", kept)}
    assert landed["view"] == ("Filings" if kept == "filings" else "Earnings calls")
    assert landed["asOf"] == (ON_FILINGS if kept == "filings" else ON_CALLS)
    assert landed["fetched"] == ([] if call is None else _get(call))
    assert landed["headers"] == ([] if call is None else [HEADER])


def test_the_tab_opens_from_a_link_on_its_word() -> None:
    """``show('company', 'LFOX', 'investor-relations', '2026Q2')``, a link or a press, writes
    the word in the hash and reads the tab with no query."""
    shown, detail, landed = _drive(
        [
            _show("LFOX", "investor-relations", "2026Q2"),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1")),
        ]
    )
    assert shown["hash"] == IR + "/2026Q2"
    assert detail["fetched"] == _get(INVESTOR)
    assert landed["page"]["drawn"] == _ir("ir 1", "2026Q2")


def test_a_call_the_company_has_none_of_is_put_right_with_no_read_of_the_tab() -> None:
    """An address naming a call the company has none of (7.1), /2026Q4 for LFOX, whose newest
    is Q3 2026, is kept until the tab's read lands, which shows the newest call, and the address
    is put right to the tab alone: the page draws the answer held on the tab alone, not faded,
    and reads the newest call's transcript, never the tab again. A link to such a call later
    does the same, reading nothing."""
    trace = _drive(
        [
            _hash("2026Q4"),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1")),
            _answer(CALL_Q3, _call()),
            _hash("2019Q2"),
        ]
    )
    hashed, _, landed, _, linked = trace
    assert hashed["hash"] == IR + "/2026Q4"
    assert landed["hash"] == IR
    assert landed["page"] == IR_OPENED | {"drawn": _ir("ir 1", None)}
    assert landed["fetched"] == _get(CALL_Q3) and landed["inFlight"] == [CALL_Q3]
    assert linked["hash"] == IR and linked["fetched"] == [] and linked["inFlight"] == []
    assert linked["page"] == IR_OPENED | {"drawn": _ir("ir 1", None)}


def test_the_row_s_date_counts_the_transcript_shown() -> None:
    """The Earnings calls view's data date (7.6) is the read's while its call's read is out,
    then the older of it and the transcript's day once it lands with words: the page draws
    again as it lands and the row's date moves."""
    trace = _drive(
        [
            _hash(),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1")),
            _answer(CALL_Q3, _call(observed="2026-10-16")),
            _switch("Filings"),
            _switch("Earnings calls"),
        ]
    )
    landed, read, filings, calls = trace[2:]
    assert landed["asOf"] == ON_CALLS
    assert read["asOf"] == "data 16 Oct 2026" and read["page"]["faded"] is False
    assert filings["asOf"] == ON_FILINGS
    assert calls["asOf"] == "data 16 Oct 2026" and calls["fetched"] == []


def test_a_change_of_call_takes_the_page_to_its_top() -> None:
    """Another call, by a link, takes the page to its top, as another report does on the
    Research tab; the same call drawn again, as its read lands, keeps the reader's place."""
    trace = _drive(
        [
            _hash("2026Q2"),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1")),
            {"do": "scroll", "top": 700},
            _answer(CALL_Q2, _call(quarter=2)),
            _hash("2026Q3"),
        ]
    )
    assert [step["scrollTop"] for step in trace[3:]] == [700, 700, 0]
    assert trace[5]["fetched"] == _get(CALL_Q3)


def test_a_change_of_the_tab_s_word_reads_nothing() -> None:
    """Review Focus 4: from /2026Q2 to /2026Q3, to /filings, to the tab alone, and a word put
    right: each change draws the answer held again, at once and not faded, with the new word,
    and never reads the tab again: a call not read before is the view's one read, its
    transcript's; one read before reads nothing. The view and the data date follow the word."""
    trace = _drive(
        [
            _hash("2026Q2"),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1")),
            _answer(CALL_Q2, _call(quarter=2)),
            _hash("2026Q3"),
            _answer(CALL_Q3, _call()),
            _hash("filings"),
            _show("LFOX", "investor-relations"),
            _hash("nonsense"),
        ]
    )
    q3, _, filings, calls, put_right = trace[4:]
    assert q3["fetched"] == _get(CALL_Q3) and q3["headers"] == [HEADER]
    for step in (filings, calls, put_right):
        assert step["fetched"] == [] and step["inFlight"] == []
    for step in (q3, filings, calls, put_right):
        assert step["notesShown"] == []
    assert q3["hash"] == IR + "/2026Q3"
    assert q3["page"] == IR_OPENED | {"drawn": _ir("ir 1", "2026Q3")}
    assert (q3["view"], q3["asOf"]) == ("Earnings calls", ON_CALLS)
    assert filings["hash"] == IR + "/filings"
    assert filings["page"] == IR_OPENED | {"drawn": _ir("ir 1", "filings")}
    assert (filings["view"], filings["asOf"]) == ("Filings", ON_FILINGS)
    assert calls["hash"] == IR
    assert calls["page"] == IR_OPENED | {"drawn": _ir("ir 1", None)}
    assert (calls["view"], calls["asOf"]) == ("Earnings calls", ON_CALLS)
    assert put_right["hash"] == IR
    assert put_right["page"] == calls["page"]


def test_the_switch_replaces_the_hash_and_reads_nothing() -> None:
    """A press of Filings replaces the hash with the tab's /filings and draws the Filings view
    on the answer held, reading nothing; a press of Earnings calls replaces it with the tab
    alone, the newest call, whose transcript is the view's one read. A press of the view shown
    changes nothing: on a call, Earnings calls keeps the call."""
    trace = _drive(
        [
            _hash("2026Q2"),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1")),
            _answer(CALL_Q2, _call(quarter=2)),
            _switch("Earnings calls"),
            _switch("Filings"),
            _switch("Filings"),
            _switch("Earnings calls"),
        ]
    )
    same, filings, again, calls = trace[4:]
    for step in (same, filings, again):
        assert step["fetched"] == [] and step["inFlight"] == []
    for step in (same, filings, again, calls):
        assert step["page"]["faded"] is False
    assert same["hash"] == IR + "/2026Q2" and same["page"]["drawn"] == _ir("ir 1", "2026Q2")
    assert filings["hash"] == IR + "/filings"
    assert filings["page"]["drawn"] == _ir("ir 1", "filings")
    assert (filings["view"], filings["asOf"]) == ("Filings", ON_FILINGS)
    assert again["hash"] == IR + "/filings" and again["page"] == filings["page"]
    assert calls["hash"] == IR
    assert calls["page"]["drawn"] == _ir("ir 1", None)
    assert (calls["view"], calls["asOf"]) == ("Earnings calls", ON_CALLS)
    assert calls["fetched"] == _get(CALL_Q3) and calls["inFlight"] == [CALL_Q3]


def test_the_filings_view_without_a_filing_list_has_no_data_date() -> None:
    """A company with no filing list on file: the Filings view's data date is none, the row
    shows no date; the Earnings calls view's is the read's."""
    trace = _drive(
        [
            _hash("filings"),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1", filings=None)),
            _switch("Earnings calls"),
        ]
    )
    assert (trace[2]["view"], trace[2]["asOf"]) == ("Filings", None)
    assert (trace[3]["view"], trace[3]["asOf"]) == ("Earnings calls", ON_CALLS)
    assert trace[3]["fetched"] == _get(CALL_Q3)


def test_a_change_of_the_word_while_the_tab_s_read_is_out_reads_nothing_more() -> None:
    """A refresh's end reads the page shown again, the detail and the tab, the page faded; a
    press of the switch then draws the new view at once, still faded, and reads nothing more:
    the read out lands on the new word. The tab's first read, out while the page shows another
    tab, takes a change of the word that a link makes the same way: it lands on the newest."""
    trace = _drive(
        [
            _hash(),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1")),
            _answer(CALL_Q3, _call()),
            AGAIN,
            _switch("Filings"),
            _answer(LFOX, _detail(190.0)),
            _answer(INVESTOR, _investor("ir 2")),
        ]
    )
    again, pressed, detail, landed = trace[4:]
    assert again["fetched"] == _get(LFOX)
    assert pressed["fetched"] == [] and pressed["inFlight"] == [LFOX]
    assert pressed["hash"] == IR + "/filings"
    assert pressed["page"] == IR_OPENED | {"faded": True, "drawn": _ir("ir 1", "filings")}
    assert detail["fetched"] == _get(INVESTOR)
    assert landed["inFlight"] == []
    assert landed["page"] == IR_OPENED | {
        "price": "$190.00",
        "drawn": _ir("ir 2", "filings", 190.0),
    }
    assert landed["hash"] == IR + "/filings"

    trace = _drive(
        [
            *OPEN,
            _hash("filings"),
            _hash("2026Q4"),
            _hash(),
            _answer(INVESTOR, _investor("ir 1")),
        ]
    )
    first, call, alone, landed = trace[3:]
    assert first["fetched"] == _get(INVESTOR)
    for step in (call, alone):
        assert step["fetched"] == [] and step["inFlight"] == [INVESTOR]
        assert step["page"] == OPENED | {"faded": True}
    assert call["hash"] == IR + "/2026Q4" and alone["hash"] == IR
    assert landed["page"] == IR_OPENED | {"drawn": _ir("ir 1", None)}
    assert landed["fetched"] == _get(CALL_Q3) and landed["inFlight"] == [CALL_Q3]


def test_the_switch_of_the_faded_tab_drops_another_tab_s_read() -> None:
    """The reader leaves the tab for another one not held, then, while its read is out, presses
    the faded tab's switch: the tab is shown again at once on the answer held, at the new view,
    and the other tab's read, landing late, is dropped; nothing is read."""
    trace = _drive(
        [
            _hash(),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1")),
            _show("LFOX", "estimates"),
            _switch("Filings"),
            _answer(ESTIMATES, _tab("estimates 1")),
        ]
    )
    other, pressed, late = trace[3:]
    assert other["fetched"] == _get(ESTIMATES)
    assert other["page"] == IR_OPENED | {"faded": True, "drawn": _ir("ir 1", None)}
    assert pressed["fetched"] == []
    assert pressed["hash"] == IR + "/filings"
    shown = IR_OPENED | {"drawn": _ir("ir 1", "filings")}
    assert pressed["page"] == shown
    assert late["page"] == shown and late["hash"] == IR + "/filings"


def test_another_tab_and_back_shows_the_tab_held() -> None:
    """The tab held is shown again with no read of it when the reader comes back to it, on the
    word the address names, whose call's transcript is the view's one read; another company's
    tab is read anew."""
    trace = _drive(
        [
            _hash("filings"),
            _answer(LFOX, _detail(182.4)),
            _answer(INVESTOR, _investor("ir 1")),
            _show("LFOX", "overview"),
            _answer(OVERVIEW, _tab("overview 1")),
            _hash("2026Q3"),
            _show("BRK.B", "investor-relations"),
        ]
    )
    overview, landed, back, other = trace[3:]
    assert overview["fetched"] == _get(OVERVIEW)
    assert landed["page"]["tab"] == "Overview"
    assert back["fetched"] == _get(CALL_Q3) and back["inFlight"] == [CALL_Q3]
    assert back["page"] == IR_OPENED | {"drawn": _ir("ir 1", "2026Q3")}
    assert (back["view"], back["asOf"]) == ("Earnings calls", ON_CALLS)
    assert other["fetched"] == _get(BRK)
    assert other["hash"] == "#company/BRK.B/investor-relations"


def test_a_vendor_read_carries_the_request_header() -> None:
    """``companyPage.readVendor``, the read of the tab's two later reads, which may call a
    vendor: a GET with the header ``X-Fairband-Request: 1``; its answer as it arrives, its
    refusal the server's sentence with the answer's status. The tab's own read carries none
    (test_the_tab_s_addresses)."""
    call = INVESTOR + "/call?year=2026&quarter=3"
    older = INVESTOR + "/filings?to=2025-10-31"
    trace = _drive(
        [
            {"do": "vendor", "url": call},
            _answer(call, {"turns": []}),
            {"do": "vendor", "url": older},
            _answer(older, {"detail": "no FMP key"}, 503),
        ]
    )
    asked, answered, again, refused = trace
    assert asked["fetched"] == _get(call)
    assert asked["headers"] == [{"X-Fairband-Request": "1"}]
    assert asked["vendor"] is None
    assert answered["vendor"] == {"answer": {"turns": []}}
    assert again["headers"] == [{"X-Fairband-Request": "1"}]
    assert refused["vendor"] == {"message": "no FMP key", "status": 503}
