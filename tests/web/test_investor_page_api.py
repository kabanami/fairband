"""The Investor relations tab's three reads (the Investor relations tab's design, 7.5, 7.6 and 8.2,
and the company page's design, 10.3), on the database of ``conftest.py``: the tab's read, from the
store alone, then the read of a call's transcript and the read of a year of filings, which answer
from the store where it holds a copy that does not change and else through the pass-throughs.

The company is ``page_payloads``' LFOX, its answers stored under the params the refresh and the
pass-throughs store them with (``fetch.page_params``). ``client`` is an app with no pass-through;
``with_passthrough`` one whose pass-through asks FMP on the mock transport of ``support.vendor``,
and which sends the request header on every call. The clock reads ``NOW``, 1 Nov 2026 at 09:30
UTC, and the pass-throughs' reuse window is 24 hours. The expected figures are the readers'
(``vendors.page_investor``) on the same payloads, whose own tests read each field: these tests
check what each read hands each reader. The key is fake."""

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
from fairband.refresh.fetch import EARNINGS_ROWS, fetch_company, page_params
from fairband.refresh.passthrough import BUSY, Passthrough, PassthroughBusy
from fairband.store.db import connect
from fairband.store.observations import insert_observations
from fairband.store.vendor import record_response
from fairband.vendors import fmp as fmp_api
from fairband.vendors import page_fmp, page_investor
from fairband.vendors.fmp import FILINGS_LIMIT, Fmp
from fairband.vendors.http import VendorHttp
from fairband.vendors.normalize_fmp import quote_observations

SYMBOL = pages.SYMBOL
DAY = NOW.date()  # 1 Nov 2026, the clock's day
AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)  # 90 minutes before NOW: the refresh's time
STALE = NOW - timedelta(hours=25)  # past the pass-throughs' reuse window
TAB = f"/api/companies/{SYMBOL}/page/investor-relations"
CALL = f"{TAB}/call"
FILINGS = f"{TAB}/filings"
Q3 = {"year": "2026", "quarter": "3"}
LAST_YEAR = date(2025, 10, 31)  # the end of the window before the refresh's
TRANSCRIPT_PATH = "/stable/earning-call-transcript"
FILING_LIST = "/stable/sec-filings-search/symbol"
FIGURES = ("epsReported", "epsEstimate", "revenueReported", "revenueEstimate")
NO_QUOTE = {"price": None, "change": None, "changePercent": None, "day": None}
BAD_QUARTER = "quarter must be 1 to 4"
BAD_TO = "to must be an ISO date from 0002-01-01 on"
# The two reads that may call a vendor, each for a call or a window the store does not hold.
VENDOR_READS = (f"{CALL}?year=2026&quarter=3", f"{FILINGS}?to=2025-10-31")
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
    _store(db_path, "transcript-dates", page_params("transcript-dates", SYMBOL), payload, at)


def _filings(
    db_path: Path,
    end: date,
    payload: Any = pages.FILINGS,
    at: datetime = AT,
    *,
    error: str | None = None,
) -> None:
    """A filing list of the 365 days to ``end``, stored as the refresh stores the window of its
    day and the pass-through any window."""
    params = page_params("sec-filings", SYMBOL, end)
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
    """Every answer the tab draws, stored as the refresh stores it: the calls newest first, each
    with its quarter's four figures where an earnings row is the call's; the refresh's filing list
    of the 365 days to its day, newest first; the next earnings day and the head's figures. No
    answer carries a ref or a response id."""
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
        "filings": {
            "from": "2025-11-01",
            "to": "2026-11-01",
            "rows": page_investor.filing_rows(pages.FILINGS),
            "truncated": False,
            "observedDay": "2026-11-01",
        },
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
    answers from the store, its lists three days old, and the vendor is never asked."""
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
    assert vendor.paths == []


def test_the_latest_window_wins_over_a_newer_copy_of_an_older_one(
    client: TestClient, db_path: Path
) -> None:
    """An agent's list of the year before, fetched after the refresh's, ends earlier and never
    stands in for it. Of two copies of the latest window the newest stands; a list stored with an
    error is passed over, though its window ends later."""
    _profile(db_path)
    _filings(db_path, DAY)
    _filings(db_path, LAST_YEAR, OLDER, at=NOW)  # an agent's, fetched later
    filings = _get(client, TAB)["filings"]
    assert (filings["from"], filings["to"]) == ("2025-11-01", "2026-11-01")
    assert filings["rows"] == page_investor.filing_rows(pages.FILINGS)
    again = pages.FILINGS[:2]
    _filings(db_path, DAY, again, at=AT + timedelta(minutes=5))
    error = {"Error Message": "Limit Reach"}
    _filings(db_path, DAY + timedelta(days=1), error, at=NOW, error="unusable payload: {...}")
    filings = _get(client, TAB)["filings"]
    assert (filings["to"], filings["rows"]) == ("2026-11-01", page_investor.filing_rows(again))


def test_a_company_with_a_profile_and_nothing_else(client: TestClient, db_path: Path) -> None:
    """Review Focus 2: a company fetched before the tab's calls, or whose calls all failed: no
    call, no filing list, no next day and no data date, and a 200."""
    _profile(db_path)
    assert _get(client, TAB) == {
        "symbol": SYMBOL,
        "dataDate": None,
        "quote": NO_QUOTE,
        "nextEarnings": None,
        "calls": [],
        "filings": None,
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


@pytest.mark.parametrize("older", ["quote", "transcript-dates", "earnings"])
def test_the_data_date_is_the_oldest_of_the_calls_view_s_answers(
    client: TestClient, db_path: Path, older: str
) -> None:
    """The oldest day among the stored answers of the Earnings calls view (7.6), as the estimates
    read counts its own: the head's quote, the list of calls and the earnings rows, each in turn
    stored a day before the rest. The profile's day and the filing list's, older still, do not
    count; the filing list carries its own day."""

    def on(answer: str) -> datetime:
        return datetime(2026, 10, 29 if answer == older else 30, 12, 0, tzinfo=UTC)

    _profile(db_path, datetime(2026, 10, 20, tzinfo=UTC))
    _quote(db_path, on("quote"))
    _calls(db_path, at=on("transcript-dates"))
    _earnings(db_path, at=on("earnings"))
    _filings(db_path, DAY, at=datetime(2026, 10, 21, tzinfo=UTC))
    body = _get(client, TAB)
    assert (body["dataDate"], body["quote"]["price"]) == ("2026-10-29", 182.4)
    assert body["filings"]["observedDay"] == "2026-10-21"


def test_a_filing_list_older_than_the_calls_keeps_its_own_day(
    client: TestClient, db_path: Path
) -> None:
    """The controller's ruling on 7.6: a filing list stored before the list of calls leaves the
    data date at the calls' day and carries its older day as its own."""
    _profile(db_path)
    _calls(db_path, at=datetime(2026, 10, 30, 12, 0, tzinfo=UTC))
    _filings(db_path, DAY, at=datetime(2026, 10, 25, 12, 0, tzinfo=UTC))
    body = _get(client, TAB)
    assert (body["dataDate"], body["filings"]["observedDay"]) == ("2026-10-30", "2026-10-25")


def test_a_list_of_calls_older_than_the_filings_sets_the_data_date(
    client: TestClient, db_path: Path
) -> None:
    """The other way round: the list of calls stored before the filing list gives the data date
    its older day, and the filing list keeps its newer day as its own."""
    _profile(db_path)
    _calls(db_path, at=datetime(2026, 10, 25, 12, 0, tzinfo=UTC))
    _filings(db_path, DAY, at=datetime(2026, 10, 30, 12, 0, tzinfo=UTC))
    body = _get(client, TAB)
    assert (body["dataDate"], body["filings"]["observedDay"]) == ("2026-10-25", "2026-10-30")


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


def test_a_past_window_is_read_from_the_store_whatever_its_age(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """The window to 31 Oct 2025, stored a year ago by an agent's list: the read answers it with
    the day it was fetched and asks no vendor."""
    _profile(db_path)
    _filings(db_path, LAST_YEAR, OLDER, at=datetime(2025, 11, 2, 14, 0, tzinfo=UTC))
    body = _get(with_passthrough, FILINGS, to="2025-10-31")
    assert body == {
        "from": "2024-10-31",
        "to": "2025-10-31",
        "rows": page_investor.filing_rows(OLDER),
        "truncated": False,
        "observedDay": "2025-11-02",
    }
    assert [row["filed"] for row in body["rows"]] == ["2025-10-28", "2025-04-29"]
    assert vendor.paths == []


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
    """Today's window may still gain filings: a copy stored past the reuse window is not read from
    the store, the pass-through asks the vendor; inside the window it reuses its copy."""
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


def test_the_two_reads_need_the_request_header(
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
        (FILINGS, "to: Field required"),
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
    past window on file are answered; a call with none, a past window not on file and today's
    window, though the refresh stored it an hour ago, are a 503."""
    _profile(db_path)
    _transcript(db_path, pages.TRANSCRIPT, AT - timedelta(days=30))
    _filings(db_path, LAST_YEAR, OLDER)
    _filings(db_path, DAY)
    for path in (VENDOR_READS[0], f"{FILINGS}?to=2025-10-31"):
        assert client.get(path, headers=HEADER).status_code == 200, path
    for path in (
        f"{CALL}?year=2026&quarter=2",
        f"{FILINGS}?to=2025-10-30",
        f"{FILINGS}?to=2026-11-01",
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
        (VENDOR_READS[0], f"{host}{TRANSCRIPT_PATH}?symbol=LFOX&year=2026&quarter=3&apikey=<key>"),
        (VENDOR_READS[1], f"{host}{FILING_LIST}?symbol=LFOX&{window}&apikey=<key> -> 403"),
    ):
        response = with_passthrough.get(path)
        status, detail = _refused(response)
        assert status == 502 and detail.startswith(starts), detail
        assert KEY not in response.text


# --- the fetch's copies ----------------------------------------------------------------------


def test_the_reads_find_what_the_fetch_stores(
    db_path: Path, with_passthrough: TestClient, vendor: Vendor, policy: Policy
) -> None:
    """The refresh's fetch of ACME over the fixtures, then the three reads: the list of calls, its
    figures, the next earnings day and the filing list of the fetch's window are found under the
    params the fetch stored them with; the newest call's transcript is read from the store, and
    the window to the fetch's day from the copy the pass-through shares. No vendor is asked."""
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
        fetch_company(conn, Fmp(http, FMP_KEY), None, "ACME", policy, NOW, [FMP_KEY])
    assert router.calls["transcript"] == 1
    tab = "/api/companies/ACME/page/investor-relations"
    body = _get(with_passthrough, tab)
    assert body["calls"][0] == {
        "fiscalYear": 2026,
        "quarter": 3,
        "date": "2026-10-28",
        "epsReported": _usd(0.51),
        "epsEstimate": _usd(0.5),
        "revenueReported": _usd(300000000),
        "revenueEstimate": _usd(300000000),
    }
    assert (body["nextEarnings"], body["dataDate"], len(body["calls"])) == (
        "2027-02-04",
        "2026-11-01",
        3,
    )
    filings = body["filings"]
    assert (filings["from"], filings["to"], len(filings["rows"])) == ("2025-11-01", "2026-11-01", 8)
    call = _get(with_passthrough, f"{tab}/call", **Q3)
    assert (call["date"], call["turns"][0]["speaker"], call["observedDay"]) == (
        "2026-10-28",
        "Operator",
        "2026-11-01",
    )
    assert filings["observedDay"] == "2026-11-01"
    assert _get(with_passthrough, f"{tab}/filings", to="2026-11-01") == filings
    assert vendor.paths == []
