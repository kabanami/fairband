"""The Investor relations tab's four reads (the Investor relations tab's design, 7.5, 7.6 and 8.2,
the company page's design, 10.3, and B-252), on the database of ``conftest.py``: the tab's read,
from the store alone, which says which of its two lists is stale; then the read of the list of
calls, the read of a call's transcript and the read of a year of filings, which answer from the
store where it holds a copy that does not change and else through the pass-throughs. No refresh
stores the tab's answers: the reads do, as a reader opens the tab.

The company is ``page_payloads``' LFOX, its answers stored under the params the pass-throughs
store them with. ``client`` is an app with no pass-through; ``with_passthrough`` one whose
pass-through asks FMP on the mock transport of ``support.vendor``, and which sends the request
header on every call. The clock reads ``NOW``, 1 Nov 2026 at 09:30 UTC, and the reuse window is
24 hours. The expected figures are the readers' (``vendors.page_investor``) on the same payloads,
whose own tests read each field: these tests check what each read hands each reader. The key is
fake."""

import json
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from refresh.vendor_double import FMP_KEY, Router
from support import page_payloads as pages
from support.vendor import KEY, Vendor
from support.web import HEADER, HOST, NOW

from fairband.policy import Policy
from fairband.refresh.fetch import EARNINGS_ROWS, fetch_company
from fairband.refresh.passthrough import BUSY, Passthrough, PassthroughBusy
from fairband.store.db import connect
from fairband.store.observations import insert_observations
from fairband.store.vendor import record_response
from fairband.vendors import fmp as fmp_api
from fairband.vendors import page_fmp, page_investor
from fairband.vendors.fmp import FILINGS_LIMIT, Fmp
from fairband.vendors.http import VendorHttp
from fairband.vendors.normalize_fmp import quote_observations
from fairband.web.filings_api import WINDOW_DAYS

SYMBOL = pages.SYMBOL
DAY = NOW.date()  # 1 Nov 2026, the clock's day
AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)  # 90 minutes before NOW: the refresh's time
STALE = NOW - timedelta(hours=25)  # past the pass-throughs' reuse window
TAB = f"/api/companies/{SYMBOL}/page/investor-relations"
CALLS = f"{TAB}/calls"
CALL = f"{TAB}/call"
FILINGS = f"{TAB}/filings"
Q3 = {"year": "2026", "quarter": "3"}
LAST_YEAR = date(2025, 10, 31)  # the end of the window before the refresh's
CALL_LIST = "/stable/earning-call-transcript-dates"
TRANSCRIPT_PATH = "/stable/earning-call-transcript"
FILING_LIST = "/stable/sec-filings-search/symbol"
FIGURES = ("epsReported", "epsEstimate", "revenueReported", "revenueEstimate")
NO_QUOTE = {"price": None, "change": None, "changePercent": None, "day": None}
BAD_QUARTER = "quarter must be 1 to 4"
BAD_TO = "to must be an ISO date from 0002-01-01 on"
FUTURE_TO = "to must be today or earlier"
NO_CALLS = "FMP answered no list of earnings calls for LFOX"
# The three reads that may call a vendor: the list of calls, and a call and a window the store
# does not hold.
VENDOR_READS = (CALLS, f"{CALL}?year=2026&quarter=3", f"{FILINGS}?to=2025-10-31")
# The filings of the window to 31 Oct 2025, the year before the refresh's.
OLDER = [
    pages.FILINGS[3] | {"filingDate": "2025-04-29 00:00:00", "acceptedDate": "2025-04-29 16:02:40"},
    pages.FILINGS[1] | {"filingDate": "2025-10-28 00:00:00", "acceptedDate": "2025-10-28 16:01:05"},
]


def _store(
    db_path: Path,
    endpoint: str,
    params: dict[str, str],
    payload: Any,
    at: datetime,
    *,
    error: str | None = None,
) -> None:
    """``payload`` stored as LFOX's HTTP 200 answer to ``endpoint`` under ``params``, observed
    ``at``."""
    with closing(connect(db_path)) as conn:
        text = json.dumps(payload)
        record_response(conn, "fmp", endpoint, params, SYMBOL, 200, text, error, at)


def _profile(db_path: Path, at: datetime = AT) -> None:
    _store(db_path, "profile", {"symbol": SYMBOL}, pages.PROFILE, at)


def _quote(db_path: Path, at: datetime = AT) -> None:
    """LFOX's quote, stored with its observations as the fetch stores them."""
    with closing(connect(db_path)) as conn:
        text = json.dumps(pages.QUOTE)
        found = record_response(
            conn, "fmp", "quote", {"symbol": SYMBOL}, SYMBOL, 200, text, None, at
        )
        insert_observations(conn, quote_observations(pages.QUOTE, SYMBOL, found, at, at))


def _earnings(db_path: Path, payload: Any = pages.EARNINGS, at: datetime = AT) -> None:
    _store(db_path, "earnings", {"symbol": SYMBOL, "limit": str(EARNINGS_ROWS)}, payload, at)


def _calls(db_path: Path, payload: Any = pages.CALL_DATES, at: datetime = AT) -> None:
    _store(db_path, "transcript-dates", {"symbol": SYMBOL}, payload, at)


def _filings(
    db_path: Path,
    end: date,
    payload: Any = pages.FILINGS,
    at: datetime = AT,
    *,
    error: str | None = None,
) -> None:
    """A filing list of the 365 days to ``end``, stored as the ``filings`` pass-through stores a
    window, and as a refresh before B-252 stored the window of its day."""
    params = {
        "symbol": SYMBOL,
        "from": (end - timedelta(days=365)).isoformat(),
        "to": end.isoformat(),
        "limit": str(FILINGS_LIMIT),
    }
    _store(db_path, "sec-filings", params, payload, at, error=error)


def _transcript(
    db_path: Path, payload: Any, at: datetime, year: int = 2026, quarter: int = 3
) -> None:
    params = {"symbol": SYMBOL, "year": str(year), "quarter": str(quarter)}
    _store(db_path, "transcript", params, payload, at)


def _stored(db_path: Path) -> int:
    """The count of the store's vendor responses."""
    with closing(connect(db_path)) as conn:
        found: int = conn.execute("SELECT COUNT(*) FROM vendor_responses").fetchone()[0]
    return found


def _get(client: TestClient, path: str, **params: str) -> Any:
    r = client.get(path, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _refused(response: httpx.Response) -> tuple[int, str]:
    return response.status_code, response.json()["detail"]


def _usd(value: float) -> dict[str, Any]:
    """A figure in US dollars as ``page_fmp.money`` gives it."""
    return {"value": value, "currency": "USD"}


def _answering(vendor: Vendor, payload: Any) -> list[dict[str, str]]:
    """Makes the vendor answer every request with ``payload``; the list it returns gathers each
    request's query parameters, the key left out."""
    asked: list[dict[str, str]] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append({k: v for k, v in request.url.params.items() if k != "apikey"})
        return httpx.Response(200, json=payload)

    vendor.answer = answer
    return asked


# --- the tab's read --------------------------------------------------------------------------


def test_the_tab_s_read_whole(client: TestClient, db_path: Path) -> None:
    """Every answer the tab draws, stored 90 minutes ago: the calls newest first, each with its
    quarter's four figures where an earnings row is the call's, and the day their list was read;
    the filing list of the 365 days to today, newest first; the next earnings day and the head's
    figures. Neither list is stale. No answer carries a ref or a response id."""
    _profile(db_path)
    _quote(db_path)
    _earnings(db_path)
    _calls(db_path)
    _filings(db_path, DAY)
    body = _get(client, TAB)
    assert body == {
        "symbol": SYMBOL,
        "dataDate": "2026-11-01",
        "quote": page_fmp.head_quote(pages.QUOTE[0]),
        "nextEarnings": "2027-01-14",
        "calls": page_investor.calls(pages.CALL_DATES, pages.EARNINGS),
        "callsDay": "2026-11-01",
        "callsStale": False,
        "callsServed": True,
        "filings": {
            "from": "2025-11-01",
            "to": "2026-11-01",
            "rows": page_investor.filing_rows(pages.FILINGS),
            "truncated": False,
            "observedDay": "2026-11-01",
        },
        "filingsStale": False,
    }
    calls = body["calls"]
    assert [(call["fiscalYear"], call["quarter"]) for call in calls] == [
        (2026, 3),
        (2026, 2),
        (2026, 1),
        (2025, 4),
        (2025, 3),
    ]
    assert calls[1] == {
        "fiscalYear": 2026,
        "quarter": 2,
        "date": "2026-07-16",
        "epsReported": _usd(1.97),
        "epsEstimate": _usd(1.9),
        "revenueReported": _usd(26710000000),
        "revenueEstimate": _usd(26050000000),
    }
    # The newest call's quarter has its estimates and no actuals; the oldest call has no row.
    assert [calls[0][name] for name in FIGURES] == [None, _usd(2.05), None, _usd(27300000000)]
    assert [calls[-1][name] for name in FIGURES] == [None] * 4
    rows = body["filings"]["rows"]
    assert [(row["form"], row["filed"]) for row in rows] == [
        ("6-K", "2026-10-30"),
        ("4", "2026-10-20"),
        ("6-K", "2026-07-17"),
        ("20-F", "2026-04-28"),
        ("SC 13G", "2026-02-11"),
    ]
    assert rows[2]["document"] is None and rows[2]["files"].startswith("https://")  # an http link
    assert (rows[4]["document"], rows[4]["files"]) == (None, None)


def test_the_tab_s_read_calls_no_vendor_and_needs_no_header(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """An app with a pass-through whose every call fails, asked with no request header: the read
    answers from the store, its lists three days old, each named stale, and the vendor is never
    asked."""
    vendor.answer = lambda request: httpx.Response(500)
    old = AT - timedelta(days=3)
    _profile(db_path)
    _earnings(db_path, at=old)
    _calls(db_path, at=old)
    _filings(db_path, DAY - timedelta(days=3), at=old)
    bare = TestClient(with_passthrough.app, base_url=HOST)
    body = _get(bare, TAB)
    assert (len(body["calls"]), body["filings"]["to"], body["dataDate"]) == (
        5,
        "2026-10-29",
        "2026-10-29",
    )
    assert (body["callsDay"], body["callsStale"], body["filingsStale"]) == (
        "2026-10-29",
        True,
        True,
    )
    assert vendor.paths == []


def test_the_latest_window_wins_over_a_newer_copy_of_an_older_one(
    client: TestClient, db_path: Path
) -> None:
    """An agent's list of the year before, fetched after the refresh's, ends earlier and never
    stands in for it. Of two copies of the latest window the newest stands; a copy of that window
    stored with an error is passed over, though it is newer still."""
    _profile(db_path)
    _filings(db_path, DAY)
    _filings(db_path, LAST_YEAR, OLDER, at=NOW)  # an agent's, fetched later
    filings = _get(client, TAB)["filings"]
    assert (filings["from"], filings["to"]) == ("2025-11-01", "2026-11-01")
    assert filings["rows"] == page_investor.filing_rows(pages.FILINGS)
    again = pages.FILINGS[:2]
    _filings(db_path, DAY, again, at=AT + timedelta(minutes=5))
    error = {"Error Message": "Limit Reach"}
    _filings(db_path, DAY, error, at=NOW, error="unusable payload: {...}")  # newer, its id too
    filings = _get(client, TAB)["filings"]
    assert (filings["to"], filings["rows"]) == ("2026-11-01", page_investor.filing_rows(again))


def test_a_whole_window_stored_before_its_last_day_is_never_the_tab_s(
    client_with_clock: Callable[[datetime], TestClient], db_path: Path
) -> None:
    """The whole-branch review's rule on the day a copy was observed: an agent's list of the 365
    days to 1 Nov 2026, asked on 15 Oct, ends latest but was stored before its last day, so it
    lacks what was filed after it; on that day, and five days after it, the tab keeps yesterday's
    refresh's, stored on its own last day. Today's refresh's window, stored on its last day like
    every refresh's, is the tab's."""
    _profile(db_path)
    yesterday = DAY - timedelta(days=1)
    _filings(db_path, yesterday, pages.FILINGS[1:], at=AT - timedelta(days=1))
    _filings(db_path, DAY, pages.FILINGS[:1], at=datetime(2026, 10, 15, 12, 0, tzinfo=UTC))
    for later in (0, 5):
        filings = _get(client_with_clock(NOW + timedelta(days=later)), TAB)["filings"]
        assert (filings["to"], filings["observedDay"]) == ("2026-10-31", "2026-10-31"), later
        assert filings["rows"] == page_investor.filing_rows(pages.FILINGS[1:])
    _filings(db_path, DAY, pages.FILINGS, at=AT)  # the refresh of today, on its last day
    filings = _get(client_with_clock(NOW), TAB)["filings"]
    assert (filings["to"], filings["observedDay"]) == ("2026-11-01", "2026-11-01")
    assert filings["rows"] == page_investor.filing_rows(pages.FILINGS)


def test_a_narrower_or_wider_list_asked_the_same_day_is_not_the_tab_s(
    client: TestClient, db_path: Path
) -> None:
    """The review's case: the refresh stores its window in the morning, then an agent asks the
    filings from 1 Oct to today, and another list from two years back to today. All three end
    today and the agents' are newer, but only a whole window of 365 days is the tab's."""
    _profile(db_path)
    _filings(db_path, DAY)
    narrower = {"symbol": SYMBOL, "from": "2026-10-01", "to": "2026-11-01", "limit": "1000"}
    wider = {"symbol": SYMBOL, "from": "2024-11-01", "to": "2026-11-01", "limit": "1000"}
    _store(db_path, "sec-filings", narrower, pages.FILINGS[:1], NOW)
    _store(db_path, "sec-filings", wider, pages.FILINGS[:2], NOW)
    filings = _get(client, TAB)["filings"]
    assert (filings["from"], filings["to"]) == ("2025-11-01", "2026-11-01")
    assert filings["rows"] == page_investor.filing_rows(pages.FILINGS)


def test_a_list_that_ends_in_the_future_is_not_the_tab_s(client: TestClient, db_path: Path) -> None:
    """The review's other case: a whole window that ends a month after today, stored directly
    since the older-window read now refuses to ask one, holds no filing yet and would beat every
    refresh until its day. The tab keeps the refresh's."""
    _profile(db_path)
    _filings(db_path, DAY)
    _filings(db_path, DAY + timedelta(days=30), [], at=NOW)
    filings = _get(client, TAB)["filings"]
    assert (filings["to"], len(filings["rows"])) == ("2026-11-01", len(pages.FILINGS))


def test_no_whole_window_on_file_is_no_filing_list(client: TestClient, db_path: Path) -> None:
    """Review Focus 1 and 2: filing lists of any other shape, and none of a whole window that
    ends by today, give the tab no filing list, and nothing throws: a narrower window, a window
    of another page size, a row whose params lack ``to``, a ``to`` that is no ISO date, and a
    whole window that ends tomorrow."""
    _profile(db_path)
    for params in (
        {"symbol": SYMBOL, "from": "2026-10-01", "to": "2026-11-01", "limit": "1000"},
        {"symbol": SYMBOL, "from": "2025-11-01", "to": "2026-11-01", "limit": "100"},
        {"symbol": SYMBOL, "from": "2025-11-01", "limit": "1000"},
        {"symbol": SYMBOL, "from": "2025-11-01", "to": "soon", "limit": "1000"},
    ):
        _store(db_path, "sec-filings", params, pages.FILINGS, AT)
    _filings(db_path, DAY + timedelta(days=1))
    body = _get(client, TAB)
    assert (body["filings"], body["calls"]) == (None, [])


def test_a_company_with_a_profile_and_nothing_else(client: TestClient, db_path: Path) -> None:
    """Review Focus 2, and every company whose tab no reader opened yet (B-252): no call, no
    filing list, each named stale so the page asks for it, no next day and no data date, and a
    200."""
    _profile(db_path)
    assert _get(client, TAB) == {
        "symbol": SYMBOL,
        "dataDate": None,
        "quote": NO_QUOTE,
        "nextEarnings": None,
        "calls": [],
        "callsDay": None,
        "callsStale": True,
        "callsServed": True,
        "filings": None,
        "filingsStale": True,
    }


def test_answers_of_the_wrong_shape(client: TestClient, db_path: Path) -> None:
    """Review Focus 1: FMP's error object, which the pass-through stored as a list of calls before
    it checked one, and earnings that are no list: the read answers, with no call and no next day.
    Then a list's rows with a quarter of 5, a fiscal year as text, no date, or no object at all
    are dropped, as are a filing list's rows with no form or no object."""
    _profile(db_path)
    _calls(db_path, {"Error Message": "Limit Reach"})
    _earnings(db_path, "not a list")
    body = _get(client, TAB)
    assert (body["calls"], body["nextEarnings"], body["filings"]) == ([], None, None)
    odd = [
        {"quarter": 5, "fiscalYear": 2026, "date": "2026-10-15"},
        {"quarter": 2, "fiscalYear": "2026", "date": "2026-07-16"},
        {"quarter": 1, "fiscalYear": 2026},
        "a row",
        pages.CALL_DATES[0],
    ]
    later = AT + timedelta(minutes=5)
    _calls(db_path, odd, at=later)
    _filings(
        db_path, DAY, [{"filingDate": "2026-10-01 00:00:00"}, "a row", pages.FILINGS[0]], later
    )
    body = _get(client, TAB)
    assert [(call["fiscalYear"], call["quarter"]) for call in body["calls"]] == [(2026, 3)]
    assert body["filings"]["rows"] == page_investor.filing_rows([pages.FILINGS[0]])


def test_a_list_of_the_vendor_s_limit_is_truncated(client: TestClient, db_path: Path) -> None:
    """The vendor answers a window's newest ``FILINGS_LIMIT`` rows at most: a list that holds as
    many is cut, so its oldest filings are missing; one row fewer is whole."""
    assert FILINGS_LIMIT == 1000
    _profile(db_path)
    full = [pages.FILINGS[0]] * FILINGS_LIMIT
    _filings(db_path, DAY, full)
    filings = _get(client, TAB)["filings"]
    assert (filings["truncated"], len(filings["rows"])) == (True, FILINGS_LIMIT)
    _filings(db_path, DAY, full[1:], at=AT + timedelta(minutes=5))
    assert _get(client, TAB)["filings"]["truncated"] is False


@pytest.mark.parametrize("older", ["quote", "earnings"])
def test_the_data_date_is_the_older_of_the_quote_and_the_earnings(
    client: TestClient, db_path: Path, older: str
) -> None:
    """The oldest day among the stored answers the read draws for both views (7.6), as the
    estimates read counts its own: the head's quote and the earnings rows, each in turn stored a
    day before the other. The profile's day, the list of calls' and the filing list's, older
    still, do not count: each list carries its own day, since the page may read a newer one."""

    def on(answer: str) -> datetime:
        return datetime(2026, 10, 29 if answer == older else 30, 12, 0, tzinfo=UTC)

    _profile(db_path, datetime(2026, 10, 20, tzinfo=UTC))
    _quote(db_path, on("quote"))
    _earnings(db_path, at=on("earnings"))
    _calls(db_path, at=datetime(2026, 10, 22, 12, 0, tzinfo=UTC))
    _filings(db_path, date(2026, 10, 21), at=datetime(2026, 10, 21, tzinfo=UTC))
    body = _get(client, TAB)
    assert (body["dataDate"], body["quote"]["price"]) == ("2026-10-29", 182.4)
    assert (body["callsDay"], body["filings"]["observedDay"]) == ("2026-10-22", "2026-10-21")


def test_a_list_alone_on_file_carries_its_day_and_sets_no_data_date(
    client: TestClient, db_path: Path
) -> None:
    """Neither list counts in the data date, whichever is older: with no quote and no earnings
    on file the read has none, and each list carries the day it was read."""
    _profile(db_path)
    _calls(db_path, at=datetime(2026, 10, 30, 12, 0, tzinfo=UTC))
    _filings(db_path, date(2026, 10, 25), at=datetime(2026, 10, 25, 12, 0, tzinfo=UTC))
    body = _get(client, TAB)
    assert body["dataDate"] is None
    assert (body["callsDay"], body["filings"]["observedDay"]) == ("2026-10-30", "2026-10-25")


@pytest.mark.parametrize(
    ("age", "stale"),
    [
        (timedelta(hours=23, minutes=59), False),
        (timedelta(hours=24), True),
        (timedelta(days=3), True),
    ],
)
def test_a_list_is_stale_from_the_reuse_window_on(
    client: TestClient, db_path: Path, age: timedelta, stale: bool
) -> None:
    """B-252: a stored list draws at once whatever its age, and the read names it stale where it
    was observed at or before the clock's time less the reuse window, 24 hours, as the overview
    names its news: the pass-through would not reuse it either, so the page asks for a newer
    one."""
    _profile(db_path)
    at = NOW - age
    _calls(db_path, at=at)
    _filings(db_path, at.date(), at=at)
    body = _get(client, TAB)
    assert (len(body["calls"]), len(body["filings"]["rows"])) == (5, 5)
    assert (body["callsStale"], body["filingsStale"]) == (stale, stale)


def test_a_list_stored_with_an_error_is_no_list_and_stale(
    client: TestClient, db_path: Path
) -> None:
    """FMP's error object, which a pass-through stores with its error an hour ago: no list of
    calls and no filing list, and each is stale, so the page asks again."""
    _profile(db_path)
    error = {"Error Message": "Limit Reach"}
    _store(db_path, "transcript-dates", {"symbol": SYMBOL}, error, AT, error="unusable payload")
    _filings(db_path, DAY, error, error="unusable payload")
    body = _get(client, TAB)
    assert (body["calls"], body["callsDay"], body["callsStale"]) == ([], None, True)
    assert (body["filings"], body["filingsStale"]) == (None, True)


def test_a_filing_list_of_a_window_that_ended_before_it_was_read_is_stale(
    client: TestClient, db_path: Path
) -> None:
    """The review's case on B-252: the newest whole window on file is an agent's list of the 365
    days to 20 Oct 2026, asked an hour ago. It ends latest, so the tab draws it at once; it never
    held the days since, so it is stale whatever its age, and the page asks for today's window.
    Before B-252 a refresh's list of its own day stood over it. A list of the window to the day
    it was read is judged by its age alone."""
    _profile(db_path)
    _filings(db_path, date(2026, 10, 20), OLDER)
    body = _get(client, TAB)
    assert (body["filings"]["to"], body["filings"]["observedDay"]) == ("2026-10-20", "2026-11-01")
    assert body["filingsStale"] is True
    _filings(db_path, DAY)
    body = _get(client, TAB)
    assert (body["filings"]["to"], body["filingsStale"]) == ("2026-11-01", False)


# --- the list of calls --------------------------------------------------------------------------


def test_the_list_of_calls_is_read_through_the_pass_through(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """B-252: a company whose tab nobody opened has no list of calls on file. The read asks the
    ``transcript-dates`` pass-through, in the store's form of the symbol, and answers the calls
    newest first, each with its quarter's figures from the stored earnings rows, and the day the
    list was read. The pass-through keeps the answer: a second read asks nothing, and the tab's
    read then draws the list from the store, not stale."""
    _profile(db_path)
    _earnings(db_path)
    asked = _answering(vendor, pages.CALL_DATES)
    first = _get(with_passthrough, "/api/companies/lfox/page/investor-relations/calls")
    assert first == {
        "symbol": SYMBOL,
        "calls": page_investor.calls(pages.CALL_DATES, pages.EARNINGS),
        "callsDay": "2026-11-01",
    }
    assert asked == [{"symbol": SYMBOL}]
    assert _get(with_passthrough, CALLS) == first
    assert vendor.paths == [CALL_LIST]
    tab = _get(with_passthrough, TAB)
    assert (tab["calls"], tab["callsDay"], tab["callsStale"]) == (
        first["calls"],
        "2026-11-01",
        False,
    )


def test_a_stale_list_of_calls_is_asked_again_and_a_fresh_one_reused(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """The pass-through's window decides: a list stored 25 hours ago is asked again, and its
    answer, the newer list, stands; inside the window the stored list answers with no call."""
    _profile(db_path)
    _calls(db_path, pages.CALL_DATES[1:], at=STALE)
    _answering(vendor, pages.CALL_DATES)
    body = _get(with_passthrough, CALLS)
    assert (len(body["calls"]), body["callsDay"]) == (5, "2026-11-01")
    assert vendor.paths == [CALL_LIST]
    _calls(db_path, pages.CALL_DATES[:2], at=NOW)
    assert len(_get(with_passthrough, CALLS)["calls"]) == 2
    assert vendor.paths == [CALL_LIST]


def test_a_list_of_calls_that_is_no_list_is_a_502(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """FMP's error object, which the pass-through stores with its error: the read fails with its
    own sentence, as the filings read does, and the next read asks again."""
    _profile(db_path)
    _answering(vendor, {"Error Message": "Limit Reach"})
    for _ in range(2):
        assert _refused(with_passthrough.get(CALLS)) == (502, NO_CALLS)
    assert vendor.paths == [CALL_LIST, CALL_LIST]


def test_a_company_with_no_call_answers_an_empty_list(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """A company FMP holds no call of answers an empty list, which is a list: kept and reused."""
    _profile(db_path)
    _answering(vendor, [])
    for _ in range(2):
        assert _get(with_passthrough, CALLS) == {
            "symbol": SYMBOL,
            "calls": [],
            "callsDay": "2026-11-01",
        }
    assert vendor.paths == [CALL_LIST]


# --- a call's transcript ---------------------------------------------------------------------


def test_a_stored_transcript_with_words_is_read_whatever_its_age(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """A copy with words stored a month ago, far past the reuse window: the read answers it and
    asks no vendor. The answer is the reader's turns, with the day the copy was fetched."""
    _profile(db_path)
    _transcript(db_path, pages.TRANSCRIPT, NOW - timedelta(days=30))
    body = _get(with_passthrough, CALL, **Q3)
    assert body == {
        "symbol": SYMBOL,
        "fiscalYear": 2026,
        "quarter": 3,
        **page_investor.transcript(pages.TRANSCRIPT),
        "observedDay": "2026-10-02",
    }
    assert (body["date"], body["questionsAt"]) == ("2026-10-15", 2)
    assert [turn["speaker"] for turn in body["turns"]] == [
        "Operator",
        "Mara Vellini",
        "Operator",
        "Ines Dalgaard",
        "Mara Vellini",
    ]
    assert vendor.paths == []


def test_a_transcript_with_words_is_never_fetched_again(
    with_passthrough: TestClient,
    client_with_clock: Callable[[datetime], TestClient],
    vendor: Vendor,
    db_path: Path,
) -> None:
    """None stored: the first read asks the vendor, in the store's form of the symbol, and keeps
    its answer; a second read, and a read three months later on an app with no pass-through,
    answer the same from the store."""
    _profile(db_path)
    asked = _answering(vendor, pages.TRANSCRIPT)
    first = _get(with_passthrough, "/api/companies/lfox/page/investor-relations/call", **Q3)
    assert (first["symbol"], first["turns"][0]["speaker"]) == (SYMBOL, "Operator")
    assert first["observedDay"] == "2026-11-01"
    assert asked == [{"symbol": SYMBOL, "year": "2026", "quarter": "3"}]
    second = _get(with_passthrough, CALL, **Q3)
    later = client_with_clock(NOW + timedelta(days=90)).get(CALL, params=Q3, headers=HEADER)
    assert second == first and later.json() == first
    assert vendor.paths == [TRANSCRIPT_PATH]


def test_a_transcript_without_words_is_asked_again_past_the_window(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """A call the vendor held no words for: inside the reuse window the pass-through's copy
    answers ``turns`` empty and no vendor is asked; past it, the vendor is asked again. FMP's
    error object, which the transcript pass-through stores as an answer, holds no words either."""
    _profile(db_path)
    asked = _answering(vendor, pages.TRANSCRIPT)
    _transcript(db_path, [], AT, quarter=2)
    inside = _get(with_passthrough, CALL, year="2026", quarter="2")
    assert inside == {
        "symbol": SYMBOL,
        "fiscalYear": 2026,
        "quarter": 2,
        "date": None,
        "turns": [],
        "questionsAt": None,
        "observedDay": "2026-11-01",
    }
    assert vendor.paths == []
    _transcript(db_path, {"Error Message": "Limit Reach"}, STALE, quarter=1)
    past = _get(with_passthrough, CALL, year="2026", quarter="1")
    assert past["turns"] == page_investor.transcript(pages.TRANSCRIPT)["turns"]
    assert asked == [{"symbol": SYMBOL, "year": "2026", "quarter": "1"}]


def test_a_transcript_the_vendor_answers_with_its_error_is_a_502(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """The whole-branch review's M-3: FMP's error object for a call, HTTP 200 with no list, which
    the transcript pass-through stores as an answer, is no call with no words: the read fails, a
    502 with its sentence, as the filings read fails on a filing list that is no list. Read again
    inside the reuse window, the pass-through's copy is the same error, and the read fails the
    same, with no further call."""
    _profile(db_path)
    _answering(vendor, {"Error Message": "Limit Reach"})
    for _ in range(2):
        refused = with_passthrough.get(CALL, params=Q3)
        assert _refused(refused) == (502, "FMP answered no transcript for LFOX")
    assert vendor.paths == [TRANSCRIPT_PATH]


@pytest.mark.parametrize("payload", [[], [pages.TRANSCRIPT[0] | {"content": ""}]])
def test_an_empty_answer_is_a_call_with_no_words(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path, payload: Any
) -> None:
    """A list from the vendor, empty or a row with no words, is a call with no words on file: a
    200 with ``turns`` empty, the page's "No transcript on file for this call.\""""
    _profile(db_path)
    _answering(vendor, payload)
    body = _get(with_passthrough, CALL, **Q3)
    assert (body["turns"], body["questionsAt"], body["observedDay"]) == ([], None, "2026-11-01")


def test_a_stored_error_object_hides_no_older_copy_with_words(
    client: TestClient, db_path: Path
) -> None:
    """FMP's error object for the call, stored as an answer after a copy with words, hides it
    not: the read answers the words, on an app with no pass-through."""
    _profile(db_path)
    _transcript(db_path, pages.TRANSCRIPT, NOW - timedelta(days=60))
    _transcript(db_path, {"Error Message": "Limit Reach"}, AT)
    body = client.get(CALL, params=Q3, headers=HEADER).json()
    assert body["turns"] == page_investor.transcript(pages.TRANSCRIPT)["turns"]
    assert body["observedDay"] == "2026-09-02"


def test_the_newest_copy_with_words_of_that_call_is_read(client: TestClient, db_path: Path) -> None:
    """A newer copy of the call without words, one with a blank content, does not hide an older
    one with words; another call's words are not this call's. An app with no pass-through, so a
    read that missed the store would be a 503."""
    _profile(db_path)
    blank = [pages.TRANSCRIPT[0] | {"content": "  "}]
    _transcript(db_path, pages.TRANSCRIPT, NOW - timedelta(days=60))
    _transcript(db_path, blank, AT)
    _transcript(db_path, pages.TRANSCRIPT, AT, quarter=2)
    body = client.get(CALL, params=Q3, headers=HEADER).json()
    assert body["turns"] == page_investor.transcript(pages.TRANSCRIPT)["turns"]
    assert body["observedDay"] == "2026-09-02"
    missed = client.get(CALL, params={"year": "2025", "quarter": "3"}, headers=HEADER)
    assert _refused(missed) == (503, "no FMP key")


# --- a year of filings -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "at",
    [datetime(2025, 11, 2, 14, 0, tzinfo=UTC), datetime(2025, 11, 1, 0, 0, 1, tzinfo=UTC)],
)
def test_a_past_window_is_read_from_the_store_whatever_its_age(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path, at: datetime
) -> None:
    """The window to 31 Oct 2025, stored a year ago by an agent's list after its last day, two
    days after or a second into the next: the read answers it with the day it was fetched and asks
    no vendor."""
    _profile(db_path)
    _filings(db_path, LAST_YEAR, OLDER, at=at)
    body = _get(with_passthrough, FILINGS, to="2025-10-31")
    assert body == {
        "from": "2024-10-31",
        "to": "2025-10-31",
        "rows": page_investor.filing_rows(OLDER),
        "truncated": False,
        "observedDay": at.date().isoformat(),
    }
    assert [row["filed"] for row in body["rows"]] == ["2025-10-28", "2025-04-29"]
    assert vendor.paths == []


def test_a_past_window_stored_on_its_last_day_is_fetched_again(
    with_passthrough: TestClient,
    client_with_clock: Callable[[datetime], TestClient],
    vendor: Vendor,
    db_path: Path,
) -> None:
    """The whole-branch review's I-1: the refresh of 31 Oct 2025 stored the window that ends that
    day, observed that day, so a filing of the day accepted after it is missing. A year and a day
    later Show older filings asks exactly that window: the copy is not used, the pass-through asks
    the vendor and keeps its answer, which, fetched after the window's last day, a read a month
    later on an app with no pass-through answers from the store, with no further call."""
    _profile(db_path)
    _filings(db_path, LAST_YEAR, OLDER, at=datetime(2025, 10, 31, 20, 0, tzinfo=UTC))
    late = pages.FILINGS[0] | {
        "filingDate": "2025-10-31 00:00:00",
        "acceptedDate": "2025-10-31 21:15:00",
    }
    asked = _answering(vendor, [late, *OLDER])
    first = _get(with_passthrough, FILINGS, to="2025-10-31")
    assert (first["to"], first["observedDay"]) == ("2025-10-31", "2026-11-01")
    assert first["rows"] == page_investor.filing_rows([late, *OLDER])
    assert asked == [
        {"symbol": SYMBOL, "from": "2024-10-31", "to": "2025-10-31", "page": "0", "limit": "1000"}
    ]
    later = client_with_clock(NOW + timedelta(days=30))
    assert later.get(FILINGS, params={"to": "2025-10-31"}, headers=HEADER).json() == first
    assert vendor.paths == [FILING_LIST]


def test_a_past_window_not_on_file_is_fetched_once(
    with_passthrough: TestClient,
    client_with_clock: Callable[[datetime], TestClient],
    vendor: Vendor,
    db_path: Path,
) -> None:
    """A list of other days that end on the same day is not the window: the pass-through asks the
    vendor for the 365 days to ``to``, in the store's form of the symbol, and keeps the answer,
    which a read a month later on an app with no pass-through answers from the store."""
    _profile(db_path)
    other = {"symbol": SYMBOL, "from": "2025-01-01", "to": "2025-10-31", "limit": "1000"}
    _store(db_path, "sec-filings", other, pages.FILINGS, AT)
    asked = _answering(vendor, OLDER)
    first = _get(
        with_passthrough, "/api/companies/lfox/page/investor-relations/filings", to="2025-10-31"
    )
    assert (first["from"], first["to"], first["observedDay"]) == (
        "2024-10-31",
        "2025-10-31",
        "2026-11-01",
    )
    assert first["rows"] == page_investor.filing_rows(OLDER)
    assert asked == [
        {"symbol": SYMBOL, "from": "2024-10-31", "to": "2025-10-31", "page": "0", "limit": "1000"}
    ]
    later = client_with_clock(NOW + timedelta(days=30))
    assert later.get(FILINGS, params={"to": "2025-10-31"}, headers=HEADER).json() == first
    assert vendor.paths == [FILING_LIST]


def test_a_window_that_ends_today_goes_through_the_pass_through(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """A ``to`` of today is answered (tomorrow's is a 400), and today's window may still gain
    filings: a copy stored past the reuse window is not read from the store, the pass-through asks
    the vendor; inside the window it reuses its copy."""
    _profile(db_path)
    _filings(db_path, DAY, pages.FILINGS[:2], at=STALE)
    _answering(vendor, pages.FILINGS)
    first = _get(with_passthrough, FILINGS, to="2026-11-01")
    assert first == {
        "from": "2025-11-01",
        "to": "2026-11-01",
        "rows": page_investor.filing_rows(pages.FILINGS),
        "truncated": False,
        "observedDay": "2026-11-01",
    }
    assert _get(with_passthrough, FILINGS, to="2026-11-01") == first
    assert vendor.paths == [FILING_LIST]


def test_with_no_to_the_window_ends_on_the_clock_s_day(
    with_passthrough: TestClient,
    client_with_clock: Callable[[datetime], TestClient],
    vendor: Vendor,
    db_path: Path,
) -> None:
    """B-252: the page asks the tab's first window with no ``to``, since the clock's day is the
    server's to say: the 365 days to it, through the pass-through, which keeps the answer. The
    tab's read then draws it from the store, not stale, and a day later it is stale."""
    _profile(db_path)
    asked = _answering(vendor, pages.FILINGS)
    first = _get(with_passthrough, FILINGS)
    assert first == {
        "from": "2025-11-01",
        "to": "2026-11-01",
        "rows": page_investor.filing_rows(pages.FILINGS),
        "truncated": False,
        "observedDay": "2026-11-01",
    }
    assert asked == [
        {"symbol": SYMBOL, "from": "2025-11-01", "to": "2026-11-01", "page": "0", "limit": "1000"}
    ]
    assert _get(with_passthrough, FILINGS) == first
    assert vendor.paths == [FILING_LIST]
    tab = _get(with_passthrough, TAB)
    assert (tab["filings"], tab["filingsStale"]) == (first, False)
    tomorrow = _get(client_with_clock(NOW + timedelta(days=1)), TAB)
    assert (tomorrow["filings"], tomorrow["filingsStale"]) == (first, True)


def test_a_window_over_a_leap_day_starts_a_year_and_a_day_before_its_end(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """The window is the 365 days to its last day, as the agents' filing list asks by default
    (``filings_api.WINDOW_DAYS``), not a calendar year."""
    assert WINDOW_DAYS == 365
    _profile(db_path)
    _answering(vendor, [])
    body = _get(with_passthrough, FILINGS, to="2024-03-01")
    assert (body["from"], body["to"]) == ("2023-03-02", "2024-03-01")


def test_a_filing_list_that_is_no_list_is_a_502(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """Review Focus 1: FMP's error object for a window, which the pass-through stores with its
    error: the read fails as the agents' filing list does, and the next read asks again."""
    _profile(db_path)
    _answering(vendor, {"Error Message": "Limit Reach"})
    for _ in range(2):
        refused = with_passthrough.get(FILINGS, params={"to": "2025-10-31"})
        assert _refused(refused) == (502, "FMP answered no filing list for LFOX")
    assert vendor.paths == [FILING_LIST, FILING_LIST]


# --- the failures ----------------------------------------------------------------------------


def test_the_three_reads_need_the_request_header(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """D11: each may call a vendor, so without ``X-Fairband-Request: 1`` it is a 403 before
    anything is read: no vendor is asked and nothing is stored. The tab's read needs none."""
    _profile(db_path)
    stored = _stored(db_path)
    bare = TestClient(with_passthrough.app, base_url=HOST)
    for path in VENDOR_READS:
        refused = bare.get(path)
        assert (refused.status_code, refused.json()) == (
            403,
            {"detail": "missing X-Fairband-Request header"},
        )
        assert bare.get(path, headers={"X-Fairband-Request": "0"}).status_code == 403
    assert (vendor.paths, _stored(db_path)) == ([], stored)
    assert bare.get(TAB).status_code == 200


NOT_A_SYMBOL = "/api/companies/a b/page/investor-relations"
NOT_WHOLE = "Input should be a valid integer, unable to parse string as an integer"


@pytest.mark.parametrize(
    ("path", "detail"),
    [
        (NOT_A_SYMBOL, "'a b' is not a symbol"),
        (f"{NOT_A_SYMBOL}/calls", "'a b' is not a symbol"),
        (f"{NOT_A_SYMBOL}/call?year=2026&quarter=3", "'a b' is not a symbol"),
        (f"{CALL}?year=soon&quarter=3", f"year: {NOT_WHOLE}"),
        (f"{CALL}?year=2026&quarter=third", f"quarter: {NOT_WHOLE}"),
        (f"{CALL}?year=2026&quarter=0", BAD_QUARTER),
        (f"{CALL}?year=2026&quarter=5", BAD_QUARTER),
        (f"{CALL}?quarter=3", "year: Field required"),
        (f"{NOT_A_SYMBOL}/filings?to=2025-10-31", "'a b' is not a symbol"),
        (f"{FILINGS}?to=soon", BAD_TO),
        (f"{FILINGS}?to=2025-02-30", BAD_TO),
        (f"{FILINGS}?to=0001-12-31", BAD_TO),  # its window would start before the calendar
        (f"{FILINGS}?to=2026-11-02", FUTURE_TO),  # tomorrow: a window that has not ended
    ],
)
def test_a_bad_request_is_a_400_before_the_profile_and_any_call(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path, path: str, detail: str
) -> None:
    """Each with its sentence, judged before the company's profile is looked for (LFOX has none
    here, a 404 otherwise): a refused request asks no vendor and stores nothing."""
    stored = _stored(db_path)
    assert _refused(with_passthrough.get(path)) == (400, detail)
    assert (vendor.paths, _stored(db_path)) == ([], stored)


def test_the_earliest_window_the_calendar_holds(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """``to`` 2 Jan 1 is the first whose 365 days start in the calendar, on its first day."""
    _profile(db_path)
    _answering(vendor, [])
    body = _get(with_passthrough, FILINGS, to="0002-01-01")
    assert (body["from"], body["to"], body["rows"]) == ("0001-01-01", "0002-01-01", [])


def test_a_company_with_no_profile_is_a_404(with_passthrough: TestClient, vendor: Vendor) -> None:
    """The page's rule (its design, 10.3): no stored profile, no page data, before any call. AAPL
    has a snapshot and no profile, and is named in the store's form."""
    for path in (TAB, *VENDOR_READS):
        assert _refused(with_passthrough.get(path)) == (404, "no page data for LFOX"), path
    aapl = with_passthrough.get("/api/companies/aapl/page/investor-relations/call", params=Q3)
    assert _refused(aapl) == (404, "no page data for AAPL")
    assert vendor.paths == []


def test_no_fmp_key_only_where_the_store_cannot_answer(client: TestClient, db_path: Path) -> None:
    """An app with no pass-through (the server has no FMP key): a call with words on file and a
    past window on file are answered; a call with none, a past window not on file, and the list
    of calls and today's window, though the store holds each from an hour ago, are a 503."""
    _profile(db_path)
    _transcript(db_path, pages.TRANSCRIPT, AT - timedelta(days=30))
    _filings(db_path, LAST_YEAR, OLDER)
    _filings(db_path, DAY)
    _calls(db_path)
    for path in (VENDOR_READS[1], f"{FILINGS}?to=2025-10-31"):
        assert client.get(path, headers=HEADER).status_code == 200, path
    for path in (
        CALLS,
        f"{CALL}?year=2026&quarter=2",
        f"{FILINGS}?to=2025-10-30",
        f"{FILINGS}?to=2026-11-01",
        FILINGS,
    ):
        assert _refused(client.get(path, headers=HEADER)) == (503, "no FMP key"), path


def test_busy_pass_throughs_are_503(
    with_passthrough: TestClient,
    passthrough: Passthrough,
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def busy(*args: Any) -> Any:
        raise PassthroughBusy(BUSY)

    _profile(db_path)
    monkeypatch.setattr(passthrough, "fetch", busy)
    for path in VENDOR_READS:
        assert _refused(with_passthrough.get(path)) == (503, BUSY), path


def test_a_failed_vendor_call_is_a_502_scrubbed(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """The vendor's sentence, the key scrubbed from it, as the pass-through route answers it."""
    _profile(db_path)
    vendor.answer = lambda request: httpx.Response(
        403, json={"Error Message": f"Invalid API KEY: {KEY}"}
    )
    host = "GET https://financialmodelingprep.com"
    window = "from=2024-10-31&to=2025-10-31&page=0&limit=1000"
    for path, starts in (
        (VENDOR_READS[0], f"{host}{CALL_LIST}?symbol=LFOX&apikey=<key> -> 403"),
        (VENDOR_READS[1], f"{host}{TRANSCRIPT_PATH}?symbol=LFOX&year=2026&quarter=3&apikey=<key>"),
        (VENDOR_READS[2], f"{host}{FILING_LIST}?symbol=LFOX&{window}&apikey=<key> -> 403"),
    ):
        response = with_passthrough.get(path)
        status, detail = _refused(response)
        assert status == 502 and detail.startswith(starts), detail
        assert KEY not in response.text


# --- the plan the key is on (``fairband.plans``) ----------------------------------------------

EARNINGS_CALLS = "FMP's Premium plan does not serve earnings calls"


def test_the_tab_s_read_says_whether_the_plan_serves_earnings_calls(
    on_premium: TestClient, with_passthrough: TestClient, client: TestClient, db_path: Path
) -> None:
    """On Premium a company has no list of calls, and ``callsServed`` is false, so the page can
    say why. On Ultimate it is true, and without a key too: nothing there says the plan."""
    _profile(db_path)
    body = _get(on_premium, TAB)
    assert (body["calls"], body["callsServed"]) == ([], False)
    assert _get(with_passthrough, TAB)["callsServed"] is True
    assert _get(client, TAB)["callsServed"] is True


def test_on_premium_the_calls_the_store_holds_are_still_read(
    on_premium: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """A key that moved from Ultimate to Premium: the store holds a list of calls and a
    transcript with words. The tab lists the calls and reads that transcript from the store; the
    read of the list of calls, and a call the store holds no words for, answer 402 with the
    plan's sentence, and FMP is never asked."""
    _profile(db_path)
    _earnings(db_path)
    _calls(db_path)
    _transcript(db_path, pages.TRANSCRIPT, AT - timedelta(days=30))
    body = _get(on_premium, TAB)
    assert (len(body["calls"]), body["callsServed"]) == (5, False)
    assert on_premium.get(VENDOR_READS[1]).status_code == 200  # fiscal 2026 Q3, with words
    for path in (CALLS, f"{CALL}?year=2026&quarter=2"):
        assert _refused(on_premium.get(path)) == (402, EARNINGS_CALLS), path
    assert vendor.paths == []


def test_on_premium_the_filings_read_goes_through_the_pass_through(
    on_premium: TestClient, vendor: Vendor, db_path: Path
) -> None:
    _profile(db_path)
    _answering(vendor, OLDER)
    assert len(_get(on_premium, FILINGS, to="2025-10-31")["rows"]) == 2
    assert len(_get(on_premium, FILINGS)["rows"]) == 2  # today's window, as the tab opens
    assert vendor.paths == [FILING_LIST, FILING_LIST]


# --- after a refresh ----------------------------------------------------------------------------


def test_a_fetch_stores_none_of_the_tab_s_answers_and_its_reads_fetch_each_once(
    db_path: Path, with_passthrough: TestClient, vendor: Vendor, policy: Policy
) -> None:
    """B-252, whole: the refresh's fetch of ACME over the fixtures asks no list of calls, no
    filings and no transcript, so the tab's read finds neither list and names both stale. The
    three reads then ask FMP once each, as a reader opens the tab, presses Filings and reads the
    newest call; the pass-throughs keep the answers, a second round asks nothing, and the tab's
    read draws both lists from the store. The calls' figures are the fetch's earnings rows'."""
    router = Router()
    with (
        VendorHttp(
            fmp_api.BASE_URL,
            [FMP_KEY],
            policy.refresh,
            transport=router.transport,
            sleep=lambda _: None,
            clock=lambda: NOW,
        ) as http,
        closing(connect(db_path)) as conn,
    ):
        fetch_company(conn, Fmp(http, FMP_KEY), "ACME", policy, NOW, [FMP_KEY])
    assert not [e for e in ("transcript-dates", "sec-filings", "transcript") if router.calls[e]]
    tab = "/api/companies/ACME/page/investor-relations"
    before = _get(with_passthrough, tab)
    assert (before["calls"], before["callsStale"]) == ([], True)
    assert (before["filings"], before["filingsStale"]) == (None, True)
    assert (before["nextEarnings"], before["dataDate"]) == ("2027-02-04", "2026-11-01")

    for _ in range(2):
        calls = _get(with_passthrough, f"{tab}/calls")
        filings = _get(with_passthrough, f"{tab}/filings")
        call = _get(with_passthrough, f"{tab}/call", **Q3)
    assert vendor.paths == [CALL_LIST, FILING_LIST, TRANSCRIPT_PATH]
    assert calls["calls"][0] == {
        "fiscalYear": 2026,
        "quarter": 3,
        "date": "2026-10-28",
        "epsReported": _usd(0.51),
        "epsEstimate": _usd(0.5),
        "revenueReported": _usd(300000000),
        "revenueEstimate": _usd(300000000),
    }
    assert (len(calls["calls"]), calls["callsDay"]) == (3, "2026-11-01")
    assert (filings["from"], filings["to"], len(filings["rows"])) == ("2025-11-01", "2026-11-01", 8)
    assert (call["date"], call["turns"][0]["speaker"], call["observedDay"]) == (
        "2026-10-28",
        "Operator",
        "2026-11-01",
    )
    after = _get(with_passthrough, tab)
    assert (after["calls"], after["callsStale"]) == (calls["calls"], False)
    assert (after["filings"], after["filingsStale"]) == (filings, False)
    assert vendor.paths == [CALL_LIST, FILING_LIST, TRANSCRIPT_PATH]
