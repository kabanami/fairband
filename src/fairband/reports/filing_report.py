"""A stored filing report read a part at a time (spec 2026-11-11, 5, 5.2, 5.3 and 5.5): the sheet
list, a sheet's rows, one cell's text and a text search, each bounded, and the cell a ``filing:``
ref names, a string cell as it is served. Pure functions over the parsed payload of FMP's
``financial-reports-json``, stored under the endpoint ``filing-report``; the routes and the
resolver read the store.

A report is a JSON object: ``symbol``, ``period``, ``year``, then one key a sheet. A sheet is a key
whose value is a list, of rows; a row is an object with one key, the row's label, whose value is
the list of the row's cells (numbers, strings, empty strings). The first row's label is the sheet's
title, with its scale (``$ in Millions``), and its cells the columns' spans (``3 Months Ended``);
a row labelled ``items`` near the top holds the columns' dates (``Sep. 30, 2026``). A title row may
hold fewer cells than there are columns, one span over two dates.

- Served text: a sheet's name, a label and a string cell are served with every run of white space,
  the no-break space among it, as one space, and the ends trimmed (``served``). Offsets and lengths
  count in the served text; the stored payload is not changed. A number cell's text is its JSON
  text (``12.5``).
- A sheet is named by its served name: every function matches the stored key by its served name,
  the first where two keys serve alike; none is ``NoSheet``. The views a route serves
  (``sheet_rows``, ``cell_text``) serve the ``sheet`` they are given before they match it, and
  answer the served name; ``cell``, ``label`` and ``column``, which read a ref, take the served
  name as the ref holds it. A later sheet whose key serves as an earlier one's cannot be reached
  by name at all: a search hit in it answers ``rowRef`` null, since its ref would resolve into the
  earlier sheet, and ``sheet_rows`` serves the earlier sheet, whose refs are its own.
- A column's words (``column``): the cell of the row ``items`` at the column, where one of the
  sheet's first three rows is labelled ``items`` and has a cell there, after the title row's cell
  at the column when the title row holds exactly as many cells as the row ``items`` (else which
  span is the column's is not known, and it is left out), the two joined with ", " (``3 Months
  Ended, Sep. 30, 2026``); with no row ``items``, the title row's cell at the column. A number or
  an empty cell gives no word; ``None`` where none does. A sheet's rows answer the words of each
  column as ``columns``, and a search hit each number cell's as its ``column``, so the agent reads
  which period or member a number is before it cites it.
- The search: case-blind, in the served text of every label and every cell; a number cell is
  matched by its JSON text, and also by the text searched with its commas removed, so ``33,165``
  finds the cell ``33165``; a text cell is matched as it reads.
- A row of any other shape (a list, an object of other keys or of a value that is no list) is
  served with ``label`` and ``rowRef`` null and one cell, the row's JSON text, served as a string
  cell is: nothing of the row is dropped, the caps hold, and it holds no cell to cite.
- The caps: 100 sheets a sheet list answer, 100 rows a sheet answer, a string cell cut at 2,000
  characters there (as ``{text, chars}``, the full length), a page of 20,000 characters of one
  cell, 20 hits of a search, 300 characters each side of a hit's match, and a search text of
  three characters or more.
- The budget: a list an answer holds (the sheets, a sheet's rows, the hits) stops before the item
  that would take the list past ``LIST_CHARS`` characters as the MCP process prints it, one item
  at least (``fitting``), and the answer says what remains (``nextRow``, ``more``). The MCP
  process prints an answer's JSON indented by two, which makes a list of small items 2.5 to 4
  times longer than its compact JSON; an item sits two levels deep in the answer, so each is
  measured as its JSON indented by two, 4 more a line, and 2 for its comma and line break
  (``_printed``). The budget holds an answer under about 40,000 characters as the agent's host
  receives it.
- An index out of range is ``OutOfRange``, "<name> is 0 to <last>", or "<name> is out of range:
  there is none" where there is no index (a sheet with no row, a row with no cell). An offset runs
  from 0 to the cell's length, so 0 is always in range.
"""

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from itertools import islice
from typing import Any

ENDPOINT = "filing-report"  # the stored endpoint a filing report is read from
SHEET_ROWS = 100
CELL_CHARS = 2_000
PAGE_CHARS = 20_000
SEARCH_HITS = 20
SEARCH_WINDOW = 300
SEARCH_MIN = 3
LIST_CHARS = 30_000  # a list's budget, as the MCP process prints it (``_printed``)
ITEMS = "items"  # the label of the row of a sheet's column dates
SHORT_TEXT = "text needs three characters or more"
# What ``cell`` answers where the report holds no cell to cite: the resolver reads it as nothing.
# A cell stored as null is a cell, ``None``.
ABSENT = object()


class NoSheet(LookupError):
    """No sheet of the report serves as the name asked for."""

    def __init__(self, name: str) -> None:
        super().__init__(f"no sheet named {name}: ask without sheet for the sheet list")


class OutOfRange(ValueError):
    """An index past its range: ``row``, ``col``, ``fromRow`` or ``offset``, and its last value,
    ``None`` or below 0 where there is none."""

    def __init__(self, name: str, last: int | None) -> None:
        if last is None or last < 0:
            super().__init__(f"{name} is out of range: there is none")
        else:
            super().__init__(f"{name} is 0 to {last}")


def served(text: str) -> str:
    """``text`` with every run of white space, the no-break space among it, as one space and the
    ends trimmed."""
    return " ".join(text.split())


def fitting(items: Sequence[Any], limit: int) -> int:
    """How many leading items of ``items`` an answer holds: at most ``limit``, and as many as keep
    the list at or under ``LIST_CHARS`` as it is printed (``_printed``); 1 at least when there is
    an item."""
    count, size = 0, 0
    for item in items[:limit]:
        size += _printed(item)
        if count and size > LIST_CHARS:
            break
        count += 1
    return count


def sheet_list(report: Mapping[str, Any], from_row: int = 0) -> dict[str, Any]:
    """The sheets from ``from_row`` in the report's order, as many as the count and the budget
    allow, each its served name, its title (the first row's label, served), its row count and the
    length of its JSON text; ``nextRow`` the next ``from_row``, or ``None`` after the last
    sheet."""
    sheets = list(_sheets(report))
    if not 0 <= from_row < len(sheets):
        raise OutOfRange("fromRow", len(sheets) - 1)
    answered = [
        {
            "name": served(key),
            "title": _title(rows),
            "rows": len(rows),
            "chars": len(json.dumps(rows, ensure_ascii=False)),
        }
        for key, rows in sheets[from_row : from_row + SHEET_ROWS]
    ]
    kept = answered[: fitting(answered, SHEET_ROWS)]
    after = from_row + len(kept)
    return {"sheets": kept, "nextRow": after if after < len(sheets) else None}


def row_ref(response_id: int, sheet: str, row: int) -> str:
    """The ref of a row of the stored report ``response_id``, the sheet by its served name with
    ``~`` written ``~0`` and ``/`` written ``~1``; a cell's ref is the row's plus ``/<col>``."""
    escaped = sheet.replace("~", "~0").replace("/", "~1")
    return f"filing:{response_id}/{escaped}/{row}"


def sheet_rows(
    report: Mapping[str, Any], response_id: int, sheet: str, from_row: int = 0
) -> dict[str, Any]:
    """The sheet's rows from ``from_row``, as many as the count and the budget allow, each with its
    index, its served label, its ref and its cells as served; ``columns`` the words of each
    column (``column``), as many as the widest row of the page holds, ``None`` where a column has
    none, so a later page names them too; ``nextRow`` the next ``from_row``, or ``None`` after the
    last row. ``sheet`` is served before it is matched, and the answer and the refs hold the served
    name."""
    sheet = served(sheet)
    rows = _sheet(report, sheet)
    if not 0 <= from_row < len(rows):
        raise OutOfRange("fromRow", len(rows) - 1)
    answered = [
        _served_row(response_id, sheet, n, rows[n])
        for n in range(from_row, min(from_row + SHEET_ROWS, len(rows)))
    ]
    kept = answered[: fitting(answered, SHEET_ROWS)]
    after = from_row + len(kept)
    width = max(len(r["cells"]) for r in kept)
    return {
        "sheet": sheet,
        "title": _title(rows),
        "columns": [_column(rows, col) for col in range(width)],
        "rows": kept,
        "nextRow": after if after < len(rows) else None,
    }


def cell_text(
    report: Mapping[str, Any], sheet: str, row: int, col: int = 0, offset: int = 0
) -> dict[str, Any]:
    """One cell's served text (a number cell's JSON text) from ``offset``, at most ``PAGE_CHARS``
    of it, with the row's served label, the text's full length and ``nextOffset``, the next
    ``offset``, or ``None`` after the text's end; ``sheet`` served before it is matched."""
    sheet = served(sheet)
    rows = _sheet(report, sheet)
    if not 0 <= row < len(rows):
        raise OutOfRange("row", len(rows) - 1)
    label, cells = _read_row(rows[row])
    if not 0 <= col < len(cells):
        raise OutOfRange("col", len(cells) - 1)
    text = _text(cells[col])
    if not 0 <= offset <= len(text):
        raise OutOfRange("offset", len(text))
    end = offset + PAGE_CHARS
    return {
        "sheet": sheet,
        "row": row,
        "col": col,
        "label": label,
        "chars": len(text),
        "offset": offset,
        "text": text[offset:end],
        "nextOffset": end if end < len(text) else None,
    }


def search(report: Mapping[str, Any], response_id: int, text: str) -> dict[str, Any]:
    """The rows whose served label or cells hold ``text`` served, without regard to case, in the
    report's order, one hit a row: as many as the count and the budget allow, and ``more`` true
    when a further row matched. A hit's place is the first cell that matches (``col``), else the
    label (``col`` ``None``); its excerpt runs ``SEARCH_WINDOW`` characters each side of the first
    match in it, cut at the text's ends, and ``offset`` is the match's place in that text. A number
    cell also matches ``text`` with its commas removed, a number as it is printed (``33,165``)."""
    needle = served(text)
    if len(needle) < SEARCH_MIN:
        raise ValueError(SHORT_TEXT)
    # Case-blind one character for one, so an offset in the served text stays its own.
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    bare = needle.replace(",", "")  # a number as it is printed, ``33,165``, as its JSON text
    printed = re.compile(re.escape(bare), re.IGNORECASE) if bare and bare != needle else None
    found = list(islice(_hits(report, response_id, pattern, printed), SEARCH_HITS + 1))
    kept = fitting(found, SEARCH_HITS)
    return {"hits": found[:kept], "more": len(found) > kept}


def cell(report: Mapping[str, Any], sheet: str, row: int, col: int) -> Any:
    """The cell at the sheet (by its served name), the row and the column: a number as it is
    stored, a string as it is served, the text the views show, so a cite of a word fits it;
    ``ABSENT`` where the sheet, the row or the cell is not there, or the row is not a label with
    its cells."""
    found = _labelled_at(report, sheet, row)
    if found is None or not 0 <= col < len(found[1]):
        return ABSENT
    value = found[1][col]
    return served(value) if isinstance(value, str) else value


def column(report: Mapping[str, Any], sheet: str, col: int) -> str | None:
    """The served words that name the column ``col`` of the sheet (by its served name): its span
    and its date, its date, or its title row's cell (module docstring); ``None`` where the sheet is
    not there or nothing names the column."""
    rows = _find(report, sheet)
    return None if rows is None else _column(rows, col)


def label(report: Mapping[str, Any], sheet: str, row: int) -> str | None:
    """The row's served label; ``None`` where the sheet or the row is not there, or the row is not
    a label with its cells."""
    found = _labelled_at(report, sheet, row)
    return None if found is None else served(found[0])


def _sheets(report: Mapping[str, Any]) -> Iterator[tuple[str, list[Any]]]:
    """Each sheet's stored key and its rows, in the report's order."""
    for key, rows in report.items():
        if isinstance(rows, list):
            yield key, rows


def _find(report: Mapping[str, Any], sheet: str) -> list[Any] | None:
    """The rows of the first sheet whose served name is ``sheet``; ``None`` for none."""
    return next((rows for key, rows in _sheets(report) if served(key) == sheet), None)


def _sheet(report: Mapping[str, Any], sheet: str) -> list[Any]:
    rows = _find(report, sheet)
    if rows is None:
        raise NoSheet(sheet)
    return rows


def _labelled(row: Any) -> tuple[str, list[Any]] | None:
    """A row's stored label and cells; ``None`` for a row of another shape."""
    if isinstance(row, Mapping) and len(row) == 1:
        [(key, cells)] = row.items()
        if isinstance(key, str) and isinstance(cells, list):
            return key, cells
    return None


def _labelled_at(report: Mapping[str, Any], sheet: str, row: int) -> tuple[str, list[Any]] | None:
    """The stored label and cells of the sheet's row; ``None`` where the sheet or the row is not
    there, or the row is of another shape."""
    rows = _find(report, sheet)
    return None if rows is None or not 0 <= row < len(rows) else _labelled(rows[row])


def _read_row(row: Any) -> tuple[str | None, list[Any]]:
    """A row's served label and its cells as stored; a row of another shape has no label and one
    cell, its JSON text."""
    found = _labelled(row)
    if found is None:
        return None, [json.dumps(row, ensure_ascii=False)]
    return served(found[0]), found[1]


def _title(rows: Sequence[Any]) -> str | None:
    """A sheet's title: its first row's served label."""
    return None if not rows else _read_row(rows[0])[0]


def _column(rows: Sequence[Any], col: int) -> str | None:
    """The words that name the column ``col`` of a sheet of ``rows`` (``column``)."""
    top = [_labelled(row) for row in rows[:3]]
    title = top[0] if top else None
    found = next(
        ((n, row[1]) for n, row in enumerate(top) if row is not None and served(row[0]) == ITEMS),
        None,
    )
    if found is None:
        return None if title is None else _word(title[1], col)
    at, dates = found
    span = None  # where the title row, not ``items`` itself, holds one cell a date
    if at > 0 and title is not None and len(title[1]) == len(dates):
        span = _word(title[1], col)
    words = [word for word in (span, _word(dates, col)) if word is not None]
    return ", ".join(words) or None


def _word(cells: Sequence[Any], col: int) -> str | None:
    """The served text of the string cell ``col``; ``None`` where there is none, or the cell is a
    number, empty or no string."""
    value = cells[col] if 0 <= col < len(cells) else None
    return (served(value) or None) if isinstance(value, str) else None


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _text(value: Any) -> str:
    """A cell's served text: a string served, anything else its JSON text (a number's, ``12.5``)."""
    return served(value) if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _served_cell(value: Any) -> Any:
    """A cell as a sheet's rows answer it: a number or a null as it is, else its served text, a
    text longer than ``CELL_CHARS`` cut, with its full length."""
    if _number(value) or value is None:
        return value
    text = _text(value)
    if len(text) > CELL_CHARS:
        return {"text": text[:CELL_CHARS], "chars": len(text)}
    return text


def _served_row(response_id: int, sheet: str, n: int, row: Any) -> dict[str, Any]:
    label, cells = _read_row(row)
    ref = None if label is None else row_ref(response_id, sheet, n)
    return {"row": n, "label": label, "rowRef": ref, "cells": [_served_cell(c) for c in cells]}


def _hits(
    report: Mapping[str, Any],
    response_id: int,
    pattern: re.Pattern[str],
    printed: re.Pattern[str] | None,
) -> Iterator[dict[str, Any]]:
    """The search's hits in the report's order, one a row, read as they are asked for. A row of
    a sheet that serves as an earlier sheet's name has no ``rowRef``: its ref would name a row of
    the earlier sheet."""
    names: set[str] = set()
    for key, rows in _sheets(report):
        sheet = served(key)
        reachable = sheet not in names
        names.add(sheet)
        for n, row in enumerate(rows):
            label, cells = _read_row(row)
            found = _first_match(pattern, printed, label, cells)
            if found is None:
                continue
            col, text, match = found
            start = max(match.start() - SEARCH_WINDOW, 0)
            cited = reachable and label is not None
            yield {
                "sheet": sheet,
                "row": n,
                "col": col,
                "label": label,
                "excerpt": text[start : match.end() + SEARCH_WINDOW],
                "offset": match.start(),
                "rowRef": row_ref(response_id, sheet, n) if cited else None,
                "numbers": [
                    {"col": i, "value": c, "column": _column(rows, i)}
                    for i, c in enumerate(cells)
                    if _number(c)
                ],
            }


def _first_match(
    pattern: re.Pattern[str],
    printed: re.Pattern[str] | None,
    label: str | None,
    cells: Sequence[Any],
) -> tuple[int | None, str, re.Match[str]] | None:
    """The first cell whose served text matches (a number cell's also by ``printed``, the text
    searched with its commas removed), else the served label (its column ``None``), with the text
    and the match; ``None`` where nothing in the row matches."""
    for col, value in enumerate(cells):
        text = _text(value)
        match = pattern.search(text)
        if match is None and printed is not None and _number(value):
            match = printed.search(text)
        if match is not None:
            return col, text, match
    if label is not None and (match := pattern.search(label)) is not None:
        return None, label, match
    return None


def _printed(item: Any) -> int:
    """The length of ``item`` as the MCP process prints it inside an answer: its JSON indented by
    two, 4 more for each of its lines (it sits two levels deep, in a list of the answer), and 2
    for the comma and the line break after it."""
    text = json.dumps(item, ensure_ascii=False, indent=2)
    return len(text) + 4 * (text.count("\n") + 1) + 2
