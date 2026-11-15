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
import pydantic_core
import pytest
from fastapi.testclient import TestClient
from support.vendor import FIXTURES, KEY, Vendor
from support.web import HEADER, HOST, NOW

from fairband.policy import Policy
from fairband.refresh.passthrough import BUSY, Passthrough, PassthroughBusy
from fairband.reports.filing_report import LIST_CHARS
from fairband.reports.refs import Resolved, resolve
from fairband.store.db import connect
from fairband.store.vendor import record_response

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


GOAL = 40_000  # the most an answer prints as, the spec's goal


def _printed(items: list[Any]) -> int:
    """A list's length as the budget measures it (the final review's A.1): each item's JSON
    indented by two, 4 more for each of its lines and 2 for its comma and line break."""
    texts = [json.dumps(item, ensure_ascii=False, indent=2) for item in items]
    return sum(len(text) + 4 * (text.count("\n") + 1) + 2 for text in texts)


def _shown(answer: Any) -> int:
    """The length of a whole answer as the MCP process prints it, indented by two."""
    return len(pydantic_core.to_json(answer, indent=2))


def _wide(cells: list[Any], rows: int = 100) -> dict[str, Any]:
    """A filing report of one sheet ``WIDE``, ``rows`` rows by 60 columns: the title row of 60
    spans, the row ``items`` of 60 dates, then rows of ``cells``."""
    dates = [f"Sep. 30, {2026 - c}" for c in range(60)]
    head = [{"WIDE (Detail) - USD ($) $ in Millions": ["3 Months Ended"] * 60}, {"items": dates}]
    body = [{f"Segment revenue, line {n}": cells} for n in range(rows - 2)]
    return {"symbol": "ACME", "period": "Q1", "year": "2027", "WIDE": head + body}


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
    list past 30,000 characters as it is printed, before 100, and ``fromRow=<nextRow>`` goes on
    with no gap and no repeat to the last row, each answer within the goal as the agent's host
    receives it; FMP's page is full, so the list is ``truncated``."""
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
    assert 0 < len(page) < 100 and _printed(page) <= LIST_CHARS
    assert first["nextRow"] == len(page)
    assert [f["link"] for f in page] == [r["link"] for r in rows[: len(page)]]
    following = with_passthrough.get(FILINGS, params={"fromRow": first["nextRow"]}).json()
    assert following["filings"][0]["link"] == rows[first["nextRow"]]["link"]  # no gap
    assert _printed([*page, following["filings"][0]]) > LIST_CHARS  # the budget ended it
    assert following["reused"] is True
    links: list[str] = []
    start: int | None = 0
    while start is not None:
        answer = with_passthrough.get(FILINGS, params={"fromRow": start}).json()
        assert _shown(answer) <= GOAL
        links += [f["link"] for f in answer["filings"]]
        start = answer["nextRow"]
    assert links == [r["link"] for r in rows]  # no gap and no repeat
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
    "query",
    [
        "from=2026-11-11&to=2025-11-11",
        "from=soon",
        "to=2026-13-01",
        "to=2026-10-31&from=",
        "to=0001-06-01",  # a year before it is before the calendar's first (C.8)
    ],
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
    assert body["nextRow"] is None
    later = with_passthrough.get(REPORT, params={**Q1, "fromRow": 3}).json()
    assert [s["name"] for s in later["sheets"]] == [ADDITIONAL, "Revenue by Product/Region"]
    assert later["nextRow"] is None
    refused = with_passthrough.get(REPORT, params={**Q1, "fromRow": 5})
    assert _refused(refused) == (400, "fromRow is 0 to 4")
    assert vendor.paths == [REPORT_JSON]


def test_a_long_sheet_list_pages(with_passthrough: TestClient, vendor: Vendor) -> None:
    """The final review's A.2: 300 sheets with titles of 70 characters, a hundred an answer, each
    within the goal, ``fromRow=<nextRow>`` going on with no gap and no repeat."""
    words = "(Detail) - USD ($) $ in Millions, Revenues by Product and by Geographic Region"
    sheets = {
        f"SHEET {n:03d}": [{f"Sheet {n:03d} {words}"[:70]: ["3 Months Ended"]}] for n in range(300)
    }
    vendor.answer = lambda request: _json(
        {"symbol": "ACME", "period": "FY", "year": "2026", **sheets}
    )
    names: list[str] = []
    start: int | None = 0
    while start is not None:
        params = {"year": "2026", "period": "FY", "fromRow": str(start)}
        answer = with_passthrough.get(REPORT, params=params).json()
        assert len(answer["sheets"]) == 100 and _shown(answer) <= GOAL
        names += [s["name"] for s in answer["sheets"]]
        start = answer["nextRow"]
    assert names == list(sheets)  # no gap and no repeat
    assert vendor.paths == [REPORT_JSON]


@pytest.mark.parametrize(
    "cells",
    [[(7 * c) % 97 for c in range(60)], ["" if c % 10 else 12.5 for c in range(60)]],
    ids=["numbers", "empty-strings"],
)
def test_a_wide_sheet_and_its_search_answer_within_the_goal(
    with_passthrough: TestClient, vendor: Vendor, cells: list[Any]
) -> None:
    """The final review's A.4: a sheet of 100 rows by 60 columns pages within the goal with no gap
    and no repeat; a search of its rows answers within the goal, the hits of rows with 60 number
    cells stopped by the budget before 20, those of mostly empty cells at 20."""
    vendor.answer = lambda request: _json(_wide(cells))
    rows: list[int] = []
    start: int | None = 0
    while start is not None:
        params = {**Q1, "sheet": "WIDE", "fromRow": str(start)}
        answer = with_passthrough.get(REPORT, params=params).json()
        assert 1 <= len(answer["rows"]) < 100 and _shown(answer) <= GOAL
        rows += [r["row"] for r in answer["rows"]]
        start = answer["nextRow"]
    assert rows == list(range(100))
    found = with_passthrough.get(SEARCH, params={**Q1, "text": "segment revenue"}).json()
    numbers = sum(not isinstance(c, str) for c in cells)
    assert len(found["hits"]) < 20 if numbers == 60 else len(found["hits"]) == 20
    assert found["more"] is True and all(len(h["numbers"]) == numbers for h in found["hits"])
    assert [h["row"] for h in found["hits"]] == list(range(2, 2 + len(found["hits"])))
    assert _printed(found["hits"]) <= LIST_CHARS and _shown(found) <= GOAL
    assert vendor.paths == [REPORT_JSON]


def test_a_note_s_wide_row_is_cut_and_its_cells_stay_in_reach(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path, policy: Policy
) -> None:
    """B-169, the live acceptance of 2026-11-11: a note's row of 3,377 cells is served as its first
    100 with ``cellCount``, and the page prints within the goal; a cell past the cut is read by
    its index and cited by its ref; a hit on a row of 400 number cells names 60 of them with
    ``numberCount``."""
    note = ["NOTE 4. " + "x" * 30_000, *("" if c % 5 else f"Cell {c}" for c in range(1, 3_377))]
    title = {"INVESTMENTS": ["Sep. 30, 2026"]}
    rows = [title, {"INVESTMENTS": note}, {"Fair value by line": list(range(400))}]
    report = {"symbol": "ACME", "period": "Q1", "year": "2027", "INVESTMENTS": rows}
    vendor.answer = lambda request: _json(report)
    sheet = {**Q1, "sheet": "INVESTMENTS"}
    answer = with_passthrough.get(REPORT, params=sheet).json()
    wide, numbers = answer["rows"][1], answer["rows"][2]
    assert (len(wide["cells"]), wide["cellCount"]) == (100, 3_377)
    assert (len(numbers["cells"]), numbers["cellCount"]) == (100, 400)
    assert "cellCount" not in answer["rows"][0]
    assert len(answer["columns"]) == 100 and answer["nextRow"] is None and _shown(answer) <= GOAL
    far = with_passthrough.get(REPORT, params={**sheet, "row": 1, "col": 3_375}).json()
    assert (far["text"], far["chars"], far["column"]) == ("Cell 3375", 9, None)
    near = with_passthrough.get(REPORT, params={**sheet, "row": 2}).json()
    assert (near["text"], near["column"]) == ("0", "Sep. 30, 2026")  # the view names its column
    with closing(connect(db_path)) as conn:
        cited = resolve(conn, "ACME", f"{numbers['rowRef']}/399", policy)
    assert cited == Resolved(399, None, None, None)
    found = with_passthrough.get(SEARCH, params={**Q1, "text": "fair value by line"}).json()
    (hit,) = found["hits"]
    assert (len(hit["numbers"]), hit["numberCount"]) == (60, 400) and _shown(found) <= GOAL


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
    assert body["columns"] == ["3 Months Ended, Sep. 30, 2026"]  # the span and the date
    with closing(connect(db_path)) as conn:
        cited = resolve(conn, "ACME", f"{row['rowRef']}/0", policy)
    assert cited == Resolved(12.5, None, None, None)
    assert vendor.paths == [REPORT_JSON]


def test_a_sheet_names_its_columns(with_passthrough: TestClient) -> None:
    """The final review's B.2: the statement's two columns by their spans and dates, on its first
    page and on a later one; a sheet with no row ``items`` by its title row's spans."""
    income = {**Q1, "sheet": "INCOME STATEMENTS"}
    named = ["3 Months Ended, Sep. 30, 2026", "3 Months Ended, Sep. 30, 2025"]
    assert with_passthrough.get(REPORT, params=income).json()["columns"] == named
    later = with_passthrough.get(REPORT, params={**income, "fromRow": 3}).json()
    assert [r["label"] for r in later["rows"]] == ["Operating income"]
    assert later["columns"] == named
    region = with_passthrough.get(REPORT, params={**Q1, "sheet": "Revenue by Product/Region"})
    assert region.json()["columns"] == ["3 Months Ended", "3 Months Ended"]


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
    assert body["hits"][1]["numbers"] == [
        {"col": 0, "value": 12.5, "column": "3 Months Ended, Sep. 30, 2026"}
    ]
    assert body["more"] is False
    assert body["hits"][1]["rowRef"] == f"filing:{body['responseId']}/{ADDITIONAL}/2"
    assert body["hits"][1]["label"] == LABEL
    assert (body["year"], body["period"], body["text"]) == (2027, "Q1", "not yet commenced")
    assert (body["symbol"], body["reused"]) == ("ACME", False)
    assert vendor.paths == [REPORT_JSON]


def test_a_lower_case_period_reads_as_upper_case(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    """The final review's C.2: ``q1`` and ``fy`` read as ``Q1`` and ``FY`` on both routes, so FMP
    is asked for the upper-case period and a later ask in either case reuses the one report."""
    asked: list[str] = []
    stored = (FIXTURES / "financial-reports-json.ACME.json").read_bytes()

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.params["period"])
        return httpx.Response(200, content=stored, headers={"Content-Type": "application/json"})

    vendor.answer = answer
    lower = with_passthrough.get(REPORT, params={"year": "2027", "period": "q1"}).json()
    assert (lower["period"], lower["reused"]) == ("Q1", False)
    upper = with_passthrough.get(REPORT, params=Q1).json()
    assert (upper["responseId"], upper["reused"]) == (lower["responseId"], True)
    searched = with_passthrough.get(SEARCH, params={**Q1, "period": "q1", "text": "lease"}).json()
    assert (searched["period"], searched["reused"]) == ("Q1", True)
    annual = {"year": "2026", "period": "fy", "text": "lease"}
    found = with_passthrough.get(SEARCH, params=annual).json()
    assert (found["period"], found["reused"]) == ("FY", False)
    sheets = with_passthrough.get(REPORT, params={"year": "2026", "period": "Fy"}).json()
    assert (sheets["period"], sheets["reused"]) == ("FY", True)
    assert asked == ["Q1", "FY"]


def test_a_sheet_with_white_space_is_read_by_its_served_name(with_passthrough: TestClient) -> None:
    """The final review's C.1: ``sheet`` is served before it is matched, so "LEASES " reads the
    sheet LEASES, and its rows' refs hold the served name."""
    body = with_passthrough.get(REPORT, params={**Q1, "sheet": " LEASES "}).json()
    assert body["sheet"] == "LEASES"
    assert body["rows"][0]["rowRef"] == f"filing:{body['responseId']}/LEASES/0"
    whole = with_passthrough.get(REPORT, params={**Q1, "sheet": "LEASES\xa0", "row": 2}).json()
    assert (whole["sheet"], whole["label"]) == ("LEASES", "LEASES")


def test_a_report_stored_long_ago_is_read_without_a_call(
    with_passthrough: TestClient, vendor: Vendor, db_path: Path
) -> None:
    """Spec 2026-11-15 10 (B-167): a filing report is reused whatever its age, so a copy stored
    400 days before the clock answers the sheet list and the search, its rows' refs naming it,
    and FMP is not asked; a copy stored with an error as long ago is not reused, and FMP is."""
    long_ago = NOW - timedelta(days=400)
    stored = (FIXTURES / "financial-reports-json.ACME.json").read_text()
    call = {"symbol": "ACME", "year": "2027", "period": "Q1"}
    unread = {"symbol": "ACME", "year": "2026", "period": "FY"}
    body = '{"Error Message": "No Data"}'  # stored with its payload, as the pass-through does
    error = f"unusable payload: {body}"
    with closing(connect(db_path)) as conn:
        old = record_response(
            conn, "fmp", "filing-report", call, "ACME", 200, stored, None, long_ago
        )
        record_response(conn, "fmp", "filing-report", unread, "ACME", 200, body, error, long_ago)
    listed = with_passthrough.get(REPORT, params=Q1).json()
    assert (listed["responseId"], listed["observedAt"], listed["reused"]) == (
        old,
        long_ago.isoformat(),
        True,
    )
    hit = with_passthrough.get(SEARCH, params={**Q1, "text": "not yet commenced"}).json()
    assert (hit["responseId"], hit["reused"]) == (old, True)
    assert hit["hits"][1]["rowRef"] == f"filing:{old}/{ADDITIONAL}/2"
    assert vendor.paths == []
    fetched = with_passthrough.get(REPORT, params={"year": "2026", "period": "FY"}).json()
    assert (fetched["reused"], fetched["observedAt"]) == (False, NOW.isoformat())
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
        ("year=2027&period=q5", 400, BAD_PERIOD),  # q1 reads as Q1 (C.2)
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
