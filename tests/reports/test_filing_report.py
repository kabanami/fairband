"""The views of a stored filing report (spec 2026-11-11, 5, 5.2, 5.3, 5.5): the served text, the
sheet list, a sheet's rows, one cell's text and a text search, each within its caps and the
budget, and the cell a ``filing:`` ref names; on reports built here in FMP's shape, synthetic."""

import json
from typing import Any

import pytest

from fairband.reports.filing_report import (
    ABSENT,
    NoSheet,
    OutOfRange,
    cell,
    cell_text,
    fitting,
    label,
    row_ref,
    search,
    served,
    sheet_list,
    sheet_rows,
)

LEASES = "Leases - Additional Informatio"
RAW_LABEL = "Additional leases, primarily for warehouses,\xa0that have  not yet commenced"
LABEL = "Additional leases, primarily for warehouses, that have not yet commenced"


def _report(**sheets: list[Any]) -> dict[str, Any]:
    """A filing report in FMP's shape: the symbol, the period and the year, then the sheets."""
    return {"symbol": "ACME", "period": "Q1", "year": "2027", **sheets}


def _compact(items: list[Any]) -> int:
    """The length of a list's compact JSON, as the budget counts it."""
    return len(json.dumps(items, ensure_ascii=False, separators=(",", ":")))


def _leases() -> dict[str, Any]:
    """The detail sheet of the leases not yet commenced: a title row and the row of $12.5 m."""
    title = {"Leases (Detail) $ in Millions": ["3 Months Ended"]}
    return _report(**{LEASES: [title, {RAW_LABEL: [12.5]}]})


def test_served_text_has_single_spaces() -> None:
    assert served("  As of\xa0 September 30,\n\n 2026 ") == "As of September 30, 2026"
    assert served(RAW_LABEL) == LABEL
    assert served(" \xa0\t ") == ""


def test_the_sheet_list_names_each_sheet_with_its_title_and_size() -> None:
    report = _report(
        **{
            "INCOME  STATEMENTS ": [
                {"INCOME STATEMENTS - USD ($) $ in Millions": ["3 Months Ended"]},
                {"Revenue": [340, 310]},
            ]
        }
    )
    [sheet] = sheet_list(report)
    assert (sheet["name"], sheet["title"], sheet["rows"]) == (
        "INCOME STATEMENTS",
        "INCOME STATEMENTS - USD ($) $ in Millions",
        2,
    )
    assert sheet["chars"] == len(json.dumps(report["INCOME  STATEMENTS "], ensure_ascii=False))
    # the sheet is asked for by its served name
    assert sheet_rows(report, 7, "INCOME STATEMENTS")["sheet"] == "INCOME STATEMENTS"


def test_two_sheets_that_serve_alike_name_the_first() -> None:
    report = _report(**{"A  B": [{"first": [1]}], "A B": [{"second": [2]}]})
    assert [s["name"] for s in sheet_list(report)] == ["A B", "A B"]
    assert sheet_rows(report, 7, "A B")["rows"][0]["label"] == "first"
    assert cell(report, "A B", 0, 0) == 1


def test_a_sheet_s_rows_carry_a_short_ref_and_the_cells() -> None:
    rows = sheet_rows(_leases(), 7, LEASES)
    assert rows["sheet"] == LEASES
    assert rows["title"] == "Leases (Detail) $ in Millions" and rows["nextRow"] is None
    assert rows["rows"][0] == {
        "row": 0,
        "label": "Leases (Detail) $ in Millions",
        "rowRef": f"filing:7/{LEASES}/0",
        "cells": ["3 Months Ended"],
    }
    assert rows["rows"][1] == {
        "row": 1,
        "label": LABEL,
        "rowRef": f"filing:7/{LEASES}/1",
        "cells": [12.5],
    }
    assert (
        row_ref(7, "Revenue by Product/Region ~ net", 3)
        == "filing:7/Revenue by Product~1Region ~0 net/3"
    )


def test_a_long_cell_is_cut_with_its_length() -> None:
    report = _report(
        NOTES=[
            {"long": ["x" * 2_500]},
            {"whole": ["y" * 2_000, "  " + "z" * 2_000 + "\xa0 ", "  a  b ", 7, ""]},
        ]
    )
    long, whole = sheet_rows(report, 7, "NOTES")["rows"]
    assert long["cells"] == [{"text": "x" * 2_000, "chars": 2_500}]
    # the length is the served text's: white space at the ends does not count
    assert whole["cells"] == ["y" * 2_000, "z" * 2_000, "a b", 7, ""]


def test_a_sheet_answers_a_hundred_rows_and_the_next() -> None:
    report = _report(BIG=[{f"line {n}": [n]} for n in range(250)])
    first = sheet_rows(report, 7, "BIG")
    assert [r["row"] for r in first["rows"]] == list(range(100)) and first["nextRow"] == 100
    assert first["title"] == "line 0"
    last = sheet_rows(report, 7, "BIG", 200)
    assert [r["row"] for r in last["rows"]] == list(range(200, 250)) and last["nextRow"] is None
    assert last["rows"][0] == {
        "row": 200,
        "label": "line 200",
        "rowRef": "filing:7/BIG/200",
        "cells": [200],
    }
    for start in (250, -1):
        with pytest.raises(OutOfRange, match=r"^fromRow is 0 to 249$"):
            sheet_rows(report, 7, "BIG", start)


def test_the_budget_ends_a_page_before_a_hundred_rows() -> None:
    """Review Focus 4: 60 rows, each one cell of 1,500 characters."""
    report = _report(NOTES=[{f"row {n}": ["x" * 1_500]} for n in range(60)])
    seen: list[int] = []
    start: int | None = 0
    while start is not None:
        page = sheet_rows(report, 7, "NOTES", start)
        assert 1 <= len(page["rows"]) < 100
        assert len(json.dumps(page["rows"], ensure_ascii=False, separators=(",", ":"))) <= 20_000
        seen += [r["row"] for r in page["rows"]]
        start = page["nextRow"]
    assert seen == list(range(60))  # no gap and no repeat
    # one item longer than the budget by itself is still served, alone
    assert fitting([{"a": "x" * 30_000}, {"b": 1}], 100) == 1 and fitting([], 100) == 0


def test_fitting_holds_the_list_at_or_under_the_budget() -> None:
    """The count stops at the limit, and at the item that would take the list's compact JSON past
    20,000 characters; a list of exactly 20,000 characters fits whole."""
    assert fitting([1, 2, 3], 2) == 2
    # quoted, 9,998 and 9,999 characters; with "[", "," and "]", 20,000; é counts as one
    items = ["é" * 9_996, "x" * 9_997]
    assert _compact(items) == 20_000 and fitting(items, 100) == 2
    assert fitting([*items, 1], 100) == 2
    assert fitting(["x" * 9_997, "x" * 9_997], 100) == 1  # 20,001 characters


def test_a_cell_page_is_twenty_thousand_characters() -> None:
    text = "a" * 20_000 + "b" * 20_000 + "c" * 5_000
    report = _report(NOTES=[{"Notes (Detail)": ["3 Months Ended"]}, {"Note  1": [text]}])
    page = cell_text(report, "NOTES", 1)
    assert {k: v for k, v in page.items() if k != "text"} == {
        "sheet": "NOTES",
        "row": 1,
        "col": 0,
        "label": "Note 1",
        "chars": 45_000,
        "offset": 0,
        "nextOffset": 20_000,
    }
    assert page["text"] == "a" * 20_000
    second = cell_text(report, "NOTES", 1, 0, 20_000)
    assert (second["text"], second["nextOffset"]) == ("b" * 20_000, 40_000)
    last = cell_text(report, "NOTES", 1, 0, 40_000)
    assert (last["text"], last["nextOffset"], last["chars"]) == ("c" * 5_000, None, 45_000)
    assert cell_text(report, "NOTES", 1, 0, 45_000)["text"] == ""  # the end is in range
    for row, col, offset, sentence in (
        (1, 0, 45_001, "offset is 0 to 45000"),
        (1, 0, -1, "offset is 0 to 45000"),
        (9, 0, 0, "row is 0 to 1"),
        (-1, 0, 0, "row is 0 to 1"),
        (1, 3, 0, "col is 0 to 0"),
    ):
        with pytest.raises(OutOfRange, match=f"^{sentence}$"):
            cell_text(report, "NOTES", row, col, offset)
    number = cell_text(_leases(), LEASES, 1)
    assert (number["text"], number["chars"], number["label"]) == ("12.5", 4, LABEL)
    # an empty cell has one offset, 0
    empty = cell_text(_report(S=[{"blank": [""]}]), "S", 0)
    assert (empty["text"], empty["chars"], empty["nextOffset"]) == ("", 0, None)


def test_an_empty_sheet_or_row_has_no_index() -> None:
    report = _report(EMPTY=[], S=[{"no cells": []}])
    assert sheet_list(report)[0] == {"name": "EMPTY", "title": None, "rows": 0, "chars": 2}
    with pytest.raises(OutOfRange, match="^fromRow is out of range: there is none$"):
        sheet_rows(report, 7, "EMPTY")
    with pytest.raises(OutOfRange, match="^row is out of range: there is none$"):
        cell_text(report, "EMPTY", 0)
    assert sheet_rows(report, 7, "S")["rows"][0]["cells"] == []
    with pytest.raises(OutOfRange, match="^col is out of range: there is none$"):
        cell_text(report, "S", 0)


def test_an_unknown_sheet_is_no_sheet() -> None:
    with pytest.raises(NoSheet, match="no sheet named Nope: ask without sheet for the sheet list"):
        sheet_rows(_report(), 7, "Nope")
    with pytest.raises(NoSheet, match="no sheet named Nope: ask without sheet for the sheet list"):
        cell_text(_report(), "Nope", 0)
    # the report's fields are no sheets
    with pytest.raises(NoSheet):
        sheet_rows(_report(), 7, "symbol")


def test_a_row_of_another_shape_is_served_as_its_json() -> None:
    report = _report(ODD=[["loose"], {"a": 1, "b": 2}, {"note": "not  a list"}])
    rows = sheet_rows(report, 7, "ODD")["rows"]
    assert [(r["label"], r["cells"], r["rowRef"]) for r in rows] == [
        (None, ['["loose"]'], None),
        (None, ['{"a": 1, "b": 2}'], None),
        (None, ['{"note": "not a list"}'], None),
    ]
    assert sheet_list(report)[0]["title"] is None
    assert cell(report, "ODD", 0, 0) is ABSENT and label(report, "ODD", 0) is None
    assert cell(report, "ODD", 2, 0) is ABSENT and label(report, "ODD", 2) is None
    page = cell_text(report, "ODD", 1)
    assert (page["label"], page["text"]) == (None, '{"a": 1, "b": 2}')
    [hit] = search(report, 7, "loose")["hits"]
    assert hit == {
        "sheet": "ODD",
        "row": 0,
        "col": 0,
        "label": None,
        "excerpt": '["loose"]',
        "offset": 2,
        "rowRef": None,
        "numbers": [],
    }


def test_a_cell_is_read_as_stored() -> None:
    report = _report(**{LEASES: [{"title": ["1  year"]}, {RAW_LABEL: [12.5, None]}]})
    assert cell(report, LEASES, 1, 0) == 12.5
    assert cell(report, LEASES, 0, 0) == "1  year"  # a string as it is stored
    assert cell(report, LEASES, 1, 1) is None  # a null cell is a cell
    assert label(report, LEASES, 1) == LABEL
    for sheet, row, col in ((LEASES, 1, 2), (LEASES, 2, 0), ("Nope", 0, 0), (LEASES, -1, 0)):
        assert cell(report, sheet, row, col) is ABSENT, (sheet, row, col)
    assert label(report, LEASES, 2) is None and label(report, "Nope", 0) is None


def test_search_finds_a_label_and_a_cell() -> None:
    needle = "not yet commenced"
    sentence = (
        "As of September 30, 2026, we had additional leases, primarily for warehouses, that had"
        " not yet commenced of $12.5 million."
    )
    note = "a" * 400 + " " + sentence + " " + "b" * 400
    detail = _leases()[LEASES]
    report = _report(
        **{"LEASES": [{"LEASES": ["3 Months Ended"]}, {"LEASES": [note]}], LEASES: detail}
    )
    found = search(report, 7, needle)
    assert found["more"] is False
    note_hit, label_hit = found["hits"]
    assert label_hit == {
        "sheet": LEASES,
        "row": 1,
        "col": None,
        "label": LABEL,
        "excerpt": LABEL,  # cut at the label's ends
        "offset": LABEL.index(needle),
        "rowRef": f"filing:7/{LEASES}/1",
        "numbers": [{"col": 0, "value": 12.5}],
    }
    at = note.index(needle)
    assert note_hit == {
        "sheet": "LEASES",
        "row": 1,
        "col": 0,
        "label": "LEASES",
        "excerpt": note[at - 300 : at + len(needle) + 300],
        "offset": at,
        "rowRef": "filing:7/LEASES/1",
        "numbers": [],
    }
    # a cell that matches is the hit's place, though the label matches too
    both = _report(S=[{"leases not yet commenced": [3, "of which not yet commenced: 2"]}])
    [hit] = search(both, 7, needle)["hits"]
    assert (hit["col"], hit["excerpt"], hit["numbers"]) == (
        1,
        "of which not yet commenced: 2",
        [{"col": 0, "value": 3}],
    )


def test_search_matches_plain_text_and_its_offset_opens_the_page() -> None:
    """Review Focus 3."""
    note = (
        "x" * 2_500
        + "  leases that had not\xa0yet commenced of $12.5 million (Detail). "
        + "y" * 500
    )
    report = _report(LEASES=[{"LEASES": [note]}])
    for needle in ("$12.5", "(Detail)", "NOT  YET commenced"):
        [hit] = search(report, 7, needle)["hits"]
        page = cell_text(report, "LEASES", hit["row"], hit["col"], hit["offset"])
        assert page["text"].lower().startswith(served(needle).lower())


def test_search_reads_a_number_by_its_json_text() -> None:
    [hit] = search(_leases(), 7, "12.5")["hits"]
    assert (hit["row"], hit["col"], hit["excerpt"], hit["offset"]) == (1, 0, "12.5", 0)


def test_search_stops_at_twenty_hits_and_at_the_budget() -> None:
    many = search(_report(S=[{f"lease {n}": [n]} for n in range(25)]), 7, "lease")
    assert [h["row"] for h in many["hits"]] == list(range(20)) and many["more"] is True
    assert many["hits"][0]["col"] is None  # the label alone matches
    exact = search(_report(S=[{f"lease {n}": [n]} for n in range(20)]), 7, "lease")
    assert len(exact["hits"]) == 20 and exact["more"] is False
    # twelve rows whose labels and excerpts make each hit about 2,500 characters
    wide_cell = "q" * 300 + " lease " + "q" * 300
    wide = _report(S=[{"z" * 1_800 + f" {n}": [wide_cell]} for n in range(12)])
    found = search(wide, 7, "lease")
    assert 1 <= len(found["hits"]) < 12 and found["more"] is True
    assert _compact(found["hits"]) <= 20_000
    assert [h["row"] for h in found["hits"]] == list(range(len(found["hits"])))
    assert all(len(json.dumps(h)) > 2_400 for h in found["hits"])


def test_a_short_search_text_is_refused() -> None:
    with pytest.raises(ValueError, match="text needs three characters or more"):
        search(_report(), 7, " ab ")
    with pytest.raises(ValueError, match="text needs three characters or more"):
        search(_report(), 7, "a\xa0\xa0")
    assert search(_report(), 7, "a b") == {"hits": [], "more": False}
