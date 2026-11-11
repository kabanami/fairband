"""The filing reads through the app (spec 2026-11-11 filings access, 5 and 11): the filing list, the
four views of a filing report and its search, with a ``Passthrough`` over FMP on the mock transport
of ``support.vendor``, which serves the synthetic ACME fixtures. ``with_passthrough`` sends the
request header on every call; ``client`` is an app with no pass-through. The key is fake."""

import json
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from support.vendor import FIXTURES, KEY, Vendor
from support.web import HEADER, HOST, NOW

from fairband.policy import Policy
from fairband.refresh.passthrough import BUSY, Passthrough, PassthroughBusy
from fairband.reports.filing_report import LIST_CHARS
from fairband.reports.refs import Resolved, resolve
from fairband.store.db import connect

FILINGS = "/api/companies/ACME/filings"
REPORT = "/api/companies/ACME/filing-report"
SEARCH = "/api/companies/ACME/filing-report/search"
Q1 = {"year": "2027", "period": "Q1"}
NEEDS_PERIOD = "a filing report needs year and period"
BAD_PERIOD = "period is FY or Q1 to Q4"
BAD_WINDOW = "from and to are ISO dates, from on or before to"
SHORT_TEXT = "text needs three characters or more"
FILING_LIST = "/stable/sec-filings-search/symbol"
REPORT_DATES = "/stable/financial-reports-dates"
REPORT_JSON = "/stable/financial-reports-json"
ADDITIONAL = "Leases - Additional Informatio"
LABEL = "Additional leases, primarily for warehouses, that have not yet commenced"


def _compact(items: Any) -> str:
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))


def _json(body: Any) -> httpx.Response:
    return httpx.Response(200, json=body)


def _refused(response: httpx.Response) -> tuple[int, str]:
    return response.status_code, response.json()["detail"]


# --- the filing list -------------------------------------------------------------------------


def test_the_filing_list_drops_the_ownership_forms_by_default(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    """Left out, ``to`` is the clock's date and ``from`` 365 days before it; the vendor is asked
    for that window, page 0 of 1,000 rows. Forms 4, 4/A and 144 are left out and counted."""
    asked: list[dict[str, str]] = []
    listed = (FIXTURES / "sec-filings-search-symbol.ACME.json").read_bytes()

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append({k: v for k, v in request.url.params.items() if k != "apikey"})
        return httpx.Response(200, content=listed, headers={"Content-Type": "application/json"})

    vendor.answer = answer
    body = with_passthrough.get("/api/companies/acme/filings").json()
    assert [f["formType"] for f in body["filings"]] == ["8-K", "10-Q", "8-K", "10-K", "DEF 14A"]
    assert (body["count"], body["leftOut"], body["truncated"], body["nextRow"]) == (
        5,
        3,
        False,
        None,
    )
    edgar = "https://www.sec.gov/Archives/edgar/data/1/000000000126000006"
    assert body["filings"][1] == {
        "formType": "10-Q",
        "filingDate": "2026-10-28",
        "acceptedDate": "2026-10-28 00:00:00",
        "link": f"{edgar}/0000000001-26-000006-index.htm",
        "finalLink": f"{edgar}/acme-20260930.htm",
    }
    today = NOW.date()
    year_before = (today - timedelta(days=365)).isoformat()
    assert (body["to"], body["from"]) == (today.isoformat(), year_before)
    assert (body["symbol"], body["responseId"], body["observedAt"], body["reused"]) == (
        "ACME",
        1,
        NOW.isoformat(),
        False,
    )
    window = {"from": year_before, "to": today.isoformat()}
    assert asked == [{"symbol": "ACME", **window, "page": "0", "limit": "1000"}]
    again = with_passthrough.get(FILINGS, params=window).json()
    assert (again["responseId"], again["reused"]) == (1, True)
    assert vendor.paths == [FILING_LIST]


def test_forms_picks_and_all_keeps_everything(with_passthrough: TestClient, vendor: Vendor) -> None:
    """``forms`` is a comma list matched whole and case-blind, or ``all``; each reads the one
    stored list."""
    picked = with_passthrough.get(FILINGS, params={"forms": "10-k,10-q"}).json()
    assert [f["formType"] for f in picked["filings"]] == ["10-Q", "10-K"]
    assert (picked["count"], picked["leftOut"], picked["nextRow"]) == (2, 6, None)
    spaced = with_passthrough.get(FILINGS, params={"forms": " 4/a , DEF 14A"}).json()
    assert [f["formType"] for f in spaced["filings"]] == ["4/A", "DEF 14A"]
    everything = with_passthrough.get(FILINGS, params={"forms": "all"}).json()
    assert [f["formType"] for f in everything["filings"]] == [
        "8-K",
        "4",
        "10-Q",
        "8-K",
        "4/A",
        "144",
        "10-K",
        "DEF 14A",
    ]
    assert (everything["count"], everything["leftOut"], everything["reused"]) == (8, 0, True)
    whole = with_passthrough.get(FILINGS, params={"forms": "8"}).json()  # not 8-K
    assert (whole["filings"], whole["count"], whole["leftOut"], whole["nextRow"]) == (
        [],
        0,
        8,
        None,
    )
    assert with_passthrough.get(FILINGS, params={"forms": "8", "fromRow": 0}).status_code == 200
    past = with_passthrough.get(FILINGS, params={"forms": "8", "fromRow": 1})
    assert _refused(past) == (400, "fromRow is 0 to 0")  # with none kept, 0 alone
    assert vendor.paths == [FILING_LIST]


def test_a_long_filing_list_pages_within_the_budget(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    """1,000 rows with links of real length: the answer stops before the row that would take the
    list's compact JSON past 20,000 characters, well before 100, and ``fromRow=<nextRow>`` goes on
    with no gap; FMP's page is full, so the list is ``truncated``."""
    edgar = "https://www.sec.gov/Archives/edgar/data/1000001"
    rows = [
        {
            "symbol": "ACME",
            "cik": "0001000001",
            "filingDate": "2026-10-30 00:00:00",
            "acceptedDate": "2026-10-30 16:05:12",
            "formType": "8-K",
            "link": f"{edgar}/000100000126{n:06d}/0001000001-26-{n:06d}-index.htm",
            "finalLink": f"{edgar}/000100000126{n:06d}/acme-8k_20261030-{n:06d}.htm",
        }
        for n in range(1000)
    ]
    vendor.answer = lambda request: _json(rows)
    first = with_passthrough.get(FILINGS).json()
    assert (first["count"], first["leftOut"], first["truncated"]) == (1000, 0, True)
    page = first["filings"]
    assert 0 < len(page) < 100 and len(_compact(page)) <= LIST_CHARS
    assert first["nextRow"] == len(page)
    assert [f["link"] for f in page] == [r["link"] for r in rows[: len(page)]]
    following = with_passthrough.get(FILINGS, params={"fromRow": first["nextRow"]}).json()
    assert following["filings"][0]["link"] == rows[first["nextRow"]]["link"]  # no gap
    assert len(_compact([*page, following["filings"][0]])) > LIST_CHARS  # the budget ended it
    assert following["reused"] is True
    for past in (1000, -1):
        refused = with_passthrough.get(FILINGS, params={"fromRow": past})
        assert _refused(refused) == (400, "fromRow is 0 to 999")
    assert vendor.paths == [FILING_LIST]


def test_a_filing_list_answers_a_hundred_rows_and_the_next(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    rows = [
        {"formType": "8-K", "filingDate": "2026-10-30 00:00:00", "link": f"l{n}"}
        for n in range(150)
    ]
    vendor.answer = lambda request: _json(rows)
    first = with_passthrough.get(FILINGS).json()
    assert (len(first["filings"]), first["nextRow"], first["count"]) == (100, 100, 150)
    assert first["truncated"] is False
    rest = with_passthrough.get(FILINGS, params={"fromRow": 100}).json()
    assert [f["link"] for f in rest["filings"]] == [f"l{n}" for n in range(100, 150)]
    assert rest["nextRow"] is None


def test_a_filing_row_is_answered_as_fmp_gave_it(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    """A row that is not an object is left out and counted; a filing date that does not start
    with a date is answered as FMP gave it; a field FMP left out is null."""
    rows = [
        "not a row",
        {"formType": "10-K", "filingDate": "Oct 28 2026"},
        {"formType": "10-Q", "filingDate": "2026-10-28T00:00:00", "acceptedDate": None},
        {"formType": "4", "filingDate": "2026-10-27 00:00:00"},
    ]
    vendor.answer = lambda request: _json(rows)
    body = with_passthrough.get(FILINGS).json()
    absent = {"acceptedDate": None, "link": None, "finalLink": None}
    assert body["filings"] == [
        {"formType": "10-K", "filingDate": "Oct 28 2026", **absent},
        {"formType": "10-Q", "filingDate": "2026-10-28", **absent},
    ]
    assert (body["count"], body["leftOut"]) == (2, 2)


@pytest.mark.parametrize(
    "query", ["from=2026-11-11&to=2025-11-11", "from=soon", "to=2026-13-01", "to=2026-10-31&from="]
)
def test_a_bad_window_is_400(with_passthrough: TestClient, vendor: Vendor, query: str) -> None:
    assert _refused(with_passthrough.get(f"{FILINGS}?{query}")) == (400, BAD_WINDOW)
    assert vendor.paths == []


def test_a_window_names_its_days(with_passthrough: TestClient, vendor: Vendor) -> None:
    """``from`` alone runs to the clock's date; ``to`` alone from 365 days before it."""
    since = with_passthrough.get(FILINGS, params={"from": "2026-06-30"}).json()
    assert (since["from"], since["to"]) == ("2026-06-30", NOW.date().isoformat())
    until = with_passthrough.get(FILINGS, params={"to": "2026-06-30"}).json()
    assert (until["from"], until["to"]) == ("2025-06-30", "2026-06-30")


# --- the filing report -----------------------------------------------------------------------


def test_the_reports_on_file_without_their_links(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    body = with_passthrough.get(REPORT).json()
    assert body["reports"] == [
        {"year": 2027, "period": "Q1"},
        {"year": 2026, "period": "Q4"},
        {"year": 2026, "period": "FY"},
    ]
    assert "link" not in json.dumps(body).lower()
    assert set(body) == {"symbol", "responseId", "observedAt", "reused", "reports"}
    assert (body["symbol"], body["responseId"], body["reused"]) == ("ACME", 1, False)
    assert vendor.paths == [REPORT_DATES]


def test_a_report_on_file_without_its_year_or_period_is_dropped(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    rows = [
        {"fiscalYear": 2027, "period": "Q1", "linkJson": "https://x"},
        {"fiscalYear": 2026},
        {"period": "FY"},
        {"fiscalYear": None, "period": "Q4"},
        ["not", "a", "row"],
        {"fiscalYear": 2025, "period": "FY"},
    ]
    vendor.answer = lambda request: _json(rows)
    body = with_passthrough.get(REPORT).json()
    assert body["reports"] == [{"year": 2027, "period": "Q1"}, {"year": 2025, "period": "FY"}]


def test_the_sheet_list(with_passthrough: TestClient, vendor: Vendor) -> None:
    body = with_passthrough.get(REPORT, params=Q1).json()
    assert [s["name"] for s in body["sheets"]] == [
        "Cover Page",
        "INCOME STATEMENTS",
        "LEASES",
        ADDITIONAL,
        "Revenue by Product/Region",
    ]
    assert body["sheets"][3]["title"] == "Leases - Additional Information (Detail) $ in Millions"
    assert body["sheets"][3]["rows"] == 4 and body["sheets"][3]["chars"] > 0
    assert (body["year"], body["period"]) == (2027, "Q1") and isinstance(body["responseId"], int)
    assert (body["symbol"], body["observedAt"], body["reused"]) == ("ACME", NOW.isoformat(), False)
    assert vendor.paths == [REPORT_JSON]


def test_a_sheet_and_a_cited_cell(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path, policy: Policy
) -> None:
    """The row's ref plus ``/0`` resolves through the report check's resolver to 12.5 (spec
    5.5); the sheet's view reads the report the sheet list stored."""
    listed = with_passthrough.get(REPORT, params=Q1).json()
    body = with_passthrough.get(REPORT, params={**Q1, "sheet": ADDITIONAL}).json()
    assert (body["sheet"], body["title"], body["nextRow"]) == (
        ADDITIONAL,
        "Leases - Additional Information (Detail) $ in Millions",
        None,
    )
    assert (body["year"], body["period"], body["symbol"]) == (2027, "Q1", "ACME")
    assert (body["responseId"], body["reused"]) == (listed["responseId"], True)
    row = body["rows"][2]
    assert (row["row"], row["label"], row["cells"]) == (2, LABEL, [12.5])
    assert row["rowRef"] == f"filing:{body['responseId']}/{ADDITIONAL}/2"
    with closing(connect(db_path)) as conn:
        cited = resolve(conn, "ACME", f"{row['rowRef']}/0", policy)
    assert cited == Resolved(12.5, None, None, None)
    assert vendor.paths == [REPORT_JSON]


def test_a_sheet_name_with_odd_characters_round_trips(
    with_passthrough: TestClient, db_path: Path, policy: Policy
) -> None:
    """Review Focus 1: "Revenue by Product/Region" as a query parameter; its rows' refs write the
    slash as ~1, and each resolves to the row's first cell."""
    sheet = "Revenue by Product/Region"
    body = with_passthrough.get(REPORT, params={**Q1, "sheet": sheet}).json()
    assert body["sheet"] == sheet
    rid = body["responseId"]
    refs = [r["rowRef"] for r in body["rows"]]
    assert refs == [f"filing:{rid}/Revenue by Product~1Region/{n}" for n in range(3)]
    with closing(connect(db_path)) as conn:
        for r in body["rows"]:
            cited = resolve(conn, "ACME", f"{r['rowRef']}/0", policy)
            assert cited == Resolved(r["cells"][0], None, None, None), r["rowRef"]
    cell = with_passthrough.get(REPORT, params={**Q1, "sheet": sheet, "row": 2, "col": 1}).json()
    assert (cell["sheet"], cell["label"], cell["text"], cell["chars"]) == (
        sheet,
        "Gadgets, other",
        "120",
        3,
    )


def test_a_long_cell_is_cut_and_paged(with_passthrough: TestClient) -> None:
    """The note's cell is cut at 2,000 characters in the sheet's rows, with its length; the cell
    view answers its whole served text, and ``offset`` starts inside it."""
    note = with_passthrough.get(REPORT, params={**Q1, "sheet": "LEASES"}).json()["rows"][2]
    [cut] = note["cells"]
    assert set(cut) == {"text", "chars"} and len(cut["text"]) == 2000 and cut["chars"] > 2100
    whole = with_passthrough.get(REPORT, params={**Q1, "sheet": "LEASES", "row": 2}).json()
    assert (whole["sheet"], whole["row"], whole["col"], whole["label"]) == (
        "LEASES",
        2,
        0,
        "LEASES",
    )
    assert (whole["offset"], whole["chars"], whole["nextOffset"]) == (0, cut["chars"], None)
    assert len(whole["text"]) == cut["chars"] and whole["text"].startswith(cut["text"])
    assert whole["text"].startswith("NOTE 9 - LEASES We have")  # the served text
    assert "Operating lease cost $ 41 $ 37" in whole["text"] and "\xa0" not in whole["text"]
    later = with_passthrough.get(
        REPORT, params={**Q1, "sheet": "LEASES", "row": 2, "offset": 2100}
    ).json()
    assert (later["offset"], later["chars"], later["nextOffset"]) == (2100, cut["chars"], None)
    assert later["text"] == whole["text"][2100:]


def test_a_cell_page_is_twenty_thousand_characters(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    text = "".join(f"{n:05d} " for n in range(7500))  # 45,000 characters
    report = {"symbol": "ACME", "period": "FY", "year": "2026", "NOTES": [{"NOTES": [text]}]}
    vendor.answer = lambda request: _json(report)
    asked = {"year": "2026", "period": "FY", "sheet": "NOTES", "row": "0"}
    first = with_passthrough.get(REPORT, params=asked).json()
    assert (len(first["text"]), first["nextOffset"], first["chars"]) == (20_000, 20_000, 44_999)
    last = with_passthrough.get(REPORT, params={**asked, "offset": "40000"}).json()
    assert (last["text"], last["nextOffset"]) == (text.strip()[40_000:], None)


def test_search_finds_the_sentence_and_the_row(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    body = with_passthrough.get(SEARCH, params={**Q1, "text": "not yet  commenced "}).json()
    assert [(h["sheet"], h["col"]) for h in body["hits"]] == [("LEASES", 0), (ADDITIONAL, None)]
    assert body["hits"][1]["numbers"] == [{"col": 0, "value": 12.5}] and body["more"] is False
    assert body["hits"][1]["rowRef"] == f"filing:{body['responseId']}/{ADDITIONAL}/2"
    assert body["hits"][1]["label"] == LABEL
    assert (body["year"], body["period"], body["text"]) == (2027, "Q1", "not yet commenced")
    assert (body["symbol"], body["reused"]) == ("ACME", False)
    assert vendor.paths == [REPORT_JSON]


def test_a_report_fmp_does_not_hold_is_404(with_passthrough: TestClient, vendor: Vendor) -> None:
    """Review Focus 2: FMP answers a period it does not hold with HTTP 200 and an error message;
    the answer is stored with its error and never reused, so a second ask calls FMP again."""
    vendor.answer = lambda request: _json({"Error Message": "No data found for ACME 2027 Q3"})
    sentence = (
        "FMP holds no filing report for ACME 2027 Q3: ask without year and period for the reports"
        " on file"
    )
    q3 = {"year": "2027", "period": "Q3"}
    for _ in range(2):
        assert _refused(with_passthrough.get(REPORT, params=q3)) == (404, sentence)
    searched = with_passthrough.get(SEARCH, params={**q3, "text": "lease"})
    assert _refused(searched) == (404, sentence)
    assert vendor.paths == [REPORT_JSON] * 3


@pytest.mark.parametrize(
    ("query", "status", "sentence"),
    [
        ("year=2027", 400, NEEDS_PERIOD),
        ("period=Q1", 400, NEEDS_PERIOD),
        ("sheet=LEASES", 400, NEEDS_PERIOD),
        ("row=1", 400, NEEDS_PERIOD),
        ("col=0", 400, NEEDS_PERIOD),
        ("offset=0", 400, NEEDS_PERIOD),
        ("fromRow=0", 400, NEEDS_PERIOD),
        ("year=2027&sheet=LEASES", 400, NEEDS_PERIOD),
        ("year=2027&period=Q5", 400, BAD_PERIOD),
        ("year=2027&period=q1", 400, BAD_PERIOD),
        (
            "year=2027&period=Q1&sheet=Nope",
            404,
            "no sheet named Nope: ask without sheet for the sheet list",
        ),
        ("year=2027&period=Q1&sheet=LEASES&row=9", 400, "row is 0 to 2"),
        ("year=2027&period=Q1&sheet=LEASES&row=-1", 400, "row is 0 to 2"),
        ("year=2027&period=Q1&sheet=LEASES&row=2&col=4", 400, "col is 0 to 0"),
        ("year=2027&period=Q1&sheet=LEASES&fromRow=3", 400, "fromRow is 0 to 2"),
        ("year=2027&period=Q1&sheet=INCOME STATEMENTS&row=2&offset=4", 400, "offset is 0 to 3"),
    ],
)
def test_the_refusals(
    with_passthrough: TestClient, vendor: Vendor, query: str, status: int, sentence: str
) -> None:
    """A parameter judged without a call refuses before any; the views' own after the fetch."""
    assert _refused(with_passthrough.get(f"{REPORT}?{query}")) == (status, sentence)
    assert vendor.paths == ([] if sentence in (NEEDS_PERIOD, BAD_PERIOD) else [REPORT_JSON])


def test_a_bad_whole_number_or_symbol_is_400(with_passthrough: TestClient, vendor: Vendor) -> None:
    status, detail = _refused(with_passthrough.get(REPORT, params={"year": "soon", "period": "Q1"}))
    assert status == 400 and detail.startswith("year: ")
    status, detail = _refused(with_passthrough.get(FILINGS, params={"fromRow": "next"}))
    assert status == 400 and detail.startswith("fromRow: ")
    for path in ("filings", "filing-report", "filing-report/search?year=2027&period=Q1&text=lease"):
        refused = with_passthrough.get(f"/api/companies/A$B/{path}")
        assert _refused(refused) == (400, "'A$B' is not a symbol"), path
    assert vendor.paths == []


def test_a_search_without_its_report_is_400(with_passthrough: TestClient, vendor: Vendor) -> None:
    for params in ({"text": "lease"}, {"year": "2027", "text": "lease"}, {"period": "Q1"}):
        assert _refused(with_passthrough.get(SEARCH, params=params)) == (400, NEEDS_PERIOD)
    assert vendor.paths == []


def test_a_short_search_text_is_400(with_passthrough: TestClient, vendor: Vendor) -> None:
    """Judged before the fetch, after the year and the period: a refused search calls no vendor
    and stores no report."""
    for params in ({**Q1, "text": "ab"}, {**Q1, "text": " a  "}, Q1):
        assert _refused(with_passthrough.get(SEARCH, params=params)) == (400, SHORT_TEXT)
    bad_period = {"year": "2027", "period": "Q5", "text": "ab"}
    assert _refused(with_passthrough.get(SEARCH, params=bad_period)) == (400, BAD_PERIOD)
    assert vendor.paths == []


def test_a_filing_list_that_is_not_a_list_is_502(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    vendor.answer = lambda request: _json({"Error Message": "Invalid symbol"})
    listed = with_passthrough.get(FILINGS)
    assert _refused(listed) == (502, "FMP answered no filing list for ACME")
    on_file = with_passthrough.get(REPORT)
    assert _refused(on_file) == (502, "FMP answered no filing reports for ACME")
    with_passthrough.get(FILINGS)
    assert vendor.paths == [FILING_LIST, REPORT_DATES, FILING_LIST]  # never reused


# --- what every route shares -----------------------------------------------------------------

PATHS = (FILINGS, REPORT, f"{SEARCH}?year=2027&period=Q1&text=lease")


def test_each_route_needs_the_request_header(with_passthrough: TestClient, vendor: Vendor) -> None:
    bare = TestClient(with_passthrough.app, base_url=HOST)
    for path in PATHS:
        assert bare.get(path).status_code == 403, path
        assert bare.get(path).json() == {"detail": "missing X-Fairband-Request header"}
        assert bare.get(path, headers={"X-Fairband-Request": "0"}).status_code == 403
    assert vendor.paths == []
    for path in PATHS:
        assert with_passthrough.get(path).status_code == 200, path


def test_without_a_pass_through_each_route_is_503(client: TestClient) -> None:
    """As the vendor route, the server's missing key is said before the parameters are read."""
    for path in (*PATHS, f"{REPORT}?year=2027", f"{FILINGS}?from=soon"):
        response = client.get(path, headers=HEADER)
        assert _refused(response) == (503, "no FMP key"), path


def test_busy_pass_throughs_are_503(
    with_passthrough: TestClient, passthrough: Passthrough, monkeypatch: pytest.MonkeyPatch
) -> None:
    def busy(*args: Any) -> Any:
        raise PassthroughBusy(BUSY)

    monkeypatch.setattr(passthrough, "fetch", busy)
    for path in PATHS:
        assert _refused(with_passthrough.get(path)) == (503, BUSY), path


def test_a_failed_vendor_call_is_502_scrubbed(with_passthrough: TestClient, vendor: Vendor) -> None:
    vendor.answer = lambda request: httpx.Response(
        403, json={"Error Message": f"Invalid API KEY: {KEY}"}
    )
    asked = (
        f"GET https://financialmodelingprep.com{FILING_LIST}?symbol=ACME&from=2025-11-01"
        "&to=2026-11-01&page=0&limit=1000&apikey=<key> -> 403 Forbidden: "
    )
    for path, starts in (
        (FILINGS, asked),
        (REPORT, f"GET https://financialmodelingprep.com{REPORT_DATES}?symbol=ACME&apikey=<key>"),
        (PATHS[2], f"GET https://financialmodelingprep.com{REPORT_JSON}?symbol=ACME&year=2027"),
    ):
        response = with_passthrough.get(path)
        status, detail = _refused(response)
        assert status == 502 and detail.startswith(starts), path
        assert KEY not in response.text


def test_no_key_in_an_answer(with_passthrough: TestClient, vendor: Vendor, db_path: Path) -> None:
    """A vendor that echoes the request's URL, key and all, in a link and in a cell: no answer of
    the three routes, and nothing stored, holds the key."""

    def echo(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.url.path == REPORT_JSON:
            return _json(
                {"symbol": "ACME", "period": "Q1", "year": "2027", "Asked": [{"Asked": [url]}]}
            )
        if request.url.path == REPORT_DATES:
            return _json([{"fiscalYear": 2027, "period": "Q1", "linkJson": url}])
        return _json([{"formType": "10-K", "link": url, "finalLink": url}])

    vendor.answer = echo
    answers = [
        with_passthrough.get(FILINGS),
        with_passthrough.get(REPORT),
        with_passthrough.get(REPORT, params=Q1),
        with_passthrough.get(REPORT, params={**Q1, "sheet": "Asked"}),
        with_passthrough.get(REPORT, params={**Q1, "sheet": "Asked", "row": "0"}),
        with_passthrough.get(SEARCH, params={**Q1, "text": "apikey"}),
    ]
    for answer in answers:
        assert answer.status_code == 200 and KEY not in answer.text, answer.url
    assert "apikey=<key>" in answers[0].json()["filings"][0]["link"]
    assert answers[5].json()["hits"][0]["sheet"] == "Asked"
    with closing(connect(db_path)) as conn:
        stored = [tuple(r) for r in conn.execute("SELECT payload, error FROM vendor_responses")]
    assert len(stored) == 3 and all(KEY not in str(row) for row in stored)
