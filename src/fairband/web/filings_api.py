"""The filing reads (spec 2026-11-11 filings access, 5; ``method.md`` 16.8): FMP's filing list and
its filing reports, fetched and stored by the ``filings``, ``filing-reports`` and
``filing-report`` pass-throughs (``fairband.refresh.passthrough``) and served a part at a time
(``fairband.reports.filing_report``). Every answer carries ``symbol``, the store's exchange form,
and ``responseId``, ``observedAt`` and ``reused`` of the stored response it was read from.

- ``GET /api/companies/{symbol}/filings?from=&to=&forms=&fromRow=`` answers ``from`` and ``to``,
  the window's ISO dates (``to`` the clock's date when left out, ``from`` ``WINDOW_DAYS`` before
  ``to``), and ``filings``, newest first as FMP lists them, each ``{formType, filingDate,
  acceptedDate, link, finalLink}``: ``filingDate`` the date part of FMP's ``YYYY-MM-DD HH:MM:SS``
  (a value that does not start with a date as FMP gave it), the others as FMP gave them, null
  where it gave none. ``forms`` is a comma list of form types matched whole and case-blind, or
  ``all``; left out or blank, every form but the ownership forms ``3``, ``4``, ``5`` and ``144``
  and their amendments (``4/A``). The list starts at ``fromRow`` of the kept filings (0 when left
  out) and holds at most ``FILING_ROWS`` within the budget; ``nextRow`` is the next ``fromRow``,
  or null. ``count`` is the filings the filter kept, ``leftOut`` the rows it dropped (a row that
  is not an object among them), and ``truncated`` true when FMP's list holds ``FILINGS_LIMIT``
  rows, so older filings of the window are missing.
- ``GET /api/companies/{symbol}/filing-report?year=&period=&sheet=&fromRow=&row=&col=&offset=``
  answers one of four views by the parameters given. Neither ``year`` nor ``period``: ``reports``,
  the filing reports on file as FMP orders them, each ``{year, period}`` from its ``fiscalYear``
  and ``period`` (a row without one of them is dropped, and no link is answered). ``year`` and
  ``period``: ``year``, ``period``, ``sheets`` from ``fromRow`` (0 when left out) and
  ``nextRow`` (``filing_report.sheet_list``). With ``sheet``: ``year``, ``period`` and the
  sheet's rows (``filing_report.sheet_rows``). With ``sheet`` and ``row``: ``year``, ``period``
  and one cell's text (``filing_report.cell_text``), ``col`` and ``offset`` 0 when left out. A
  parameter the view does not read is not read: ``row`` without ``sheet`` answers the sheet list,
  ``fromRow`` with ``row`` the cell.
- ``GET /api/companies/{symbol}/filing-report/search?year=&period=&text=`` answers ``year``,
  ``period``, ``text`` (the text searched, served), ``hits`` and ``more``
  (``filing_report.search``).

The refusals, in the order they are judged. Each route may call a vendor, so a request carries
``X-Fairband-Request: 1``, else 403 before anything else is read (``app``, D11). A value the
parameters' types refuse, a ``year`` or an index that is not a whole number, is the framework's
400 (``year: ...``, ``app``). Without a pass-through (the server has no FMP key), a 503, "no FMP
key", before the symbol and the other parameters are read, as the vendor route answers it. A
symbol that is not one is a 400 with its sentence. Then the parameters judged before any call,
so a refused request calls no vendor and stores nothing, each a 400: ``sheet``, ``row``, ``col``,
``offset`` or ``fromRow`` without ``year`` and ``period``, one of them without the other, and on
the search either missing, ``NEEDS_PERIOD``; a ``period`` other than ``FY`` and ``Q1`` to ``Q4``,
``BAD_PERIOD``; a search text shorter than ``SEARCH_MIN`` (three) characters once served,
``SHORT_TEXT``; a ``from`` or a ``to`` that is no ISO date, or ``from`` after ``to``,
``BAD_WINDOW``. Then the fetch: every slot taken, a 503 with the pass-through's ``BUSY``; a failed
vendor call a 502 with its sentence, scrubbed. Then what FMP answered: a report it does not hold
(``{"Error Message": ...}``, stored with its error and never reused) a 404, ``NO_REPORT``; a
filing list or a list of reports that is not a list a 502, ``NO_LIST`` or ``NO_REPORTS``. Then the
view's own: a sheet no sheet serves as, a 404 (``NoSheet``); a ``row``, ``col``, ``offset`` or
``fromRow`` out of range, a 400, "<name> is 0 to <last>" (``OutOfRange``; on the filing list,
with no filing kept, 0 alone is in range).

The routes are sync ones, as the vendor route is: FastAPI runs them on its thread pool, where a
vendor call waits at most ten seconds for one of the pass-through's four slots, then for its slot
in the limiter the refresh worker's runs share.
"""

import re
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query

from fairband.policy.settings import exchange_symbol
from fairband.refresh.passthrough import (
    BAD_PERIOD,
    BAD_WINDOW,
    FILING_PERIODS,
    NEEDS_PERIOD,
    Fetched,
    Passthrough,
    PassthroughBusy,
)
from fairband.reports.filing_report import (
    SEARCH_MIN,
    SHORT_TEXT,
    NoSheet,
    OutOfRange,
    cell_text,
    fitting,
    search,
    served,
    sheet_list,
    sheet_rows,
)
from fairband.vendors.fmp import FILINGS_LIMIT
from fairband.vendors.http import VendorError
from fairband.web.vendor_api import NO_FMP_KEY

NO_REPORT = (
    "FMP holds no filing report for {symbol} {year} {period}: ask without year and period for the"
    " reports on file"
)
NO_LIST = "FMP answered no filing list for {symbol}"
NO_REPORTS = "FMP answered no filing reports for {symbol}"
FILING_ROWS = 100  # the filings a filing-list answer holds at most, within the budget
WINDOW_DAYS = 365  # the filing list's window when ``from`` is left out
ALL_FORMS = "ALL"
OWNERSHIP_FORMS = ("3", "4", "5", "144")  # left out by default, with their amendments
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


def add_filing_routes(
    app: FastAPI, passthrough: Passthrough | None, clock: Callable[[], datetime]
) -> None:
    """Register the filing list, the filing report's views and its search; ``clock`` gives the
    filing list's default ``to``."""

    @app.get("/api/companies/{symbol}/filings")
    def filings(
        symbol: str,
        start: Annotated[str | None, Query(alias="from")] = None,
        end: Annotated[str | None, Query(alias="to")] = None,
        forms: str | None = None,
        from_row: Annotated[int | None, Query(alias="fromRow")] = None,
    ) -> dict[str, Any]:
        if passthrough is None:
            raise HTTPException(503, NO_FMP_KEY)
        company = _symbol(symbol)
        end = clock().date().isoformat() if end is None else end
        start = _year_before(end) if start is None else start
        fetched = _fetch(passthrough, "filings", company, {"from": start, "to": end})
        if fetched.row.error is not None:
            raise HTTPException(502, NO_LIST.format(symbol=company))
        rows: list[Any] = fetched.payload
        named = _forms(forms)
        kept = [_filing(row) for row in rows if isinstance(row, Mapping) and _kept(row, named)]
        first = 0 if from_row is None else from_row
        last = max(len(kept) - 1, 0)  # with no filing kept, 0 alone is in range
        if not 0 <= first <= last:
            raise HTTPException(400, str(OutOfRange("fromRow", last)))
        page = kept[first : first + FILING_ROWS]
        answered = page[: fitting(page, FILING_ROWS)]
        after = first + len(answered)
        return {
            **_head(company, fetched),
            "from": fetched.row.params["from"],
            "to": fetched.row.params["to"],
            "filings": answered,
            "nextRow": after if after < len(kept) else None,
            "count": len(kept),
            "leftOut": len(rows) - len(kept),
            "truncated": len(rows) >= FILINGS_LIMIT,
        }

    @app.get("/api/companies/{symbol}/filing-report")
    def filing_report(
        symbol: str,
        year: int | None = None,
        period: str | None = None,
        sheet: str | None = None,
        from_row: Annotated[int | None, Query(alias="fromRow")] = None,
        row: int | None = None,
        col: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        if passthrough is None:
            raise HTTPException(503, NO_FMP_KEY)
        company = _symbol(symbol)
        if year is None and period is None:
            if any(given is not None for given in (sheet, from_row, row, col, offset)):
                raise HTTPException(400, NEEDS_PERIOD)
            on_file = _fetch(passthrough, "filing-reports", company, {})
            if on_file.row.error is not None:
                raise HTTPException(502, NO_REPORTS.format(symbol=company))
            return {**_head(company, on_file), "reports": _reports(on_file.payload)}
        fetched = _report(passthrough, company, year, period)
        report, response_id = fetched.payload, fetched.row.id
        head = {**_head(company, fetched), "year": year, "period": period}
        try:
            if sheet is None:
                return {**head, **sheet_list(report, from_row or 0)}
            if row is None:
                return {**head, **sheet_rows(report, response_id, sheet, from_row or 0)}
            return {**head, **cell_text(report, sheet, row, col or 0, offset or 0)}
        except NoSheet as exc:
            raise HTTPException(404, str(exc)) from None
        except OutOfRange as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/companies/{symbol}/filing-report/search")
    def filing_search(
        symbol: str,
        year: int | None = None,
        period: str | None = None,
        text: str | None = None,
    ) -> dict[str, Any]:
        if passthrough is None:
            raise HTTPException(503, NO_FMP_KEY)
        company = _symbol(symbol)
        # Judged before the fetch, so a refused search calls no vendor and stores no report.
        if year is None or period is None:
            raise HTTPException(400, NEEDS_PERIOD)
        if period not in FILING_PERIODS:
            raise HTTPException(400, BAD_PERIOD)
        needle = served(text or "")
        if len(needle) < SEARCH_MIN:
            raise HTTPException(400, SHORT_TEXT)
        fetched = _report(passthrough, company, year, period)
        found = search(fetched.payload, fetched.row.id, needle)
        return {**_head(company, fetched), "year": year, "period": period, "text": needle, **found}


def _symbol(symbol: str) -> str:
    """The symbol in the store's exchange form, as the vendor route reads it; a 400 when it is
    not one."""
    try:
        return exchange_symbol(symbol)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


def _fetch(passthrough: Passthrough, kind: str, symbol: str, params: dict[str, str]) -> Fetched:
    """The kind's one stored response; a parameter refused before any call is a 400, every slot
    taken a 503 and a failed call a 502."""
    try:
        return passthrough.fetch(kind, symbol, params)[kind]
    except ValueError as exc:  # NEEDS_PERIOD, BAD_PERIOD, BAD_WINDOW
        raise HTTPException(400, str(exc)) from None
    except PassthroughBusy as exc:
        raise HTTPException(503, str(exc)) from None
    except VendorError as exc:
        raise HTTPException(502, str(exc)) from None


def _report(passthrough: Passthrough, symbol: str, year: int | None, period: str | None) -> Fetched:
    """The stored filing report of ``year`` and ``period``; FMP holding none is a 404."""
    given = {"year": year, "period": period}
    params = {name: str(value) for name, value in given.items() if value is not None}
    fetched = _fetch(passthrough, "filing-report", symbol, params)
    if fetched.row.error is not None:
        raise HTTPException(404, NO_REPORT.format(symbol=symbol, year=year, period=period))
    return fetched


def _head(symbol: str, fetched: Fetched) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "responseId": fetched.row.id,
        "observedAt": fetched.row.observed_at.isoformat(),
        "reused": fetched.reused,
    }


def _year_before(end: str) -> str:
    """``WINDOW_DAYS`` before the ISO date ``end``; ``BAD_WINDOW`` when it is no date."""
    try:
        return (date.fromisoformat(end) - timedelta(days=WINDOW_DAYS)).isoformat()
    except ValueError:
        raise HTTPException(400, BAD_WINDOW) from None


def _forms(forms: str | None) -> frozenset[str] | None:
    """The form types the comma list ``forms`` names, trimmed and upper-cased; ``None``, the
    default filter, when it names none (left out or blank)."""
    named = frozenset(form.strip().upper() for form in (forms or "").split(","))
    return (named - {""}) or None


def _kept(row: Mapping[str, Any], forms: frozenset[str] | None) -> bool:
    """Whether the filter keeps the filing: a form ``forms`` names, matched whole and
    case-blind, or any form when it is ``all``; by default every form but the ownership forms
    and their amendments."""
    form = str(row.get("formType") or "").strip().upper()
    if forms is None:
        return form.removesuffix("/A") not in OWNERSHIP_FORMS
    return forms == {ALL_FORMS} or form in forms


def _filing(row: Mapping[str, Any]) -> dict[str, Any]:
    """A filing as the list answers it: ``filingDate`` the date part of FMP's ``YYYY-MM-DD
    HH:MM:SS``, a value that does not start with a date as FMP gave it; the rest as FMP gave it,
    ``None`` where it gave nothing."""
    filed = row.get("filingDate")
    if isinstance(filed, str) and _DAY.match(filed):
        try:
            filed = date.fromisoformat(filed[:10]).isoformat()
        except ValueError:
            pass  # no date: as FMP gave it
    return {
        "formType": row.get("formType"),
        "filingDate": filed,
        "acceptedDate": row.get("acceptedDate"),
        "link": row.get("link"),
        "finalLink": row.get("finalLink"),
    }


def _reports(rows: list[Any]) -> list[dict[str, Any]]:
    """Each filing report on file as ``{year, period}``, its links dropped; a row without both
    is left out."""
    return [
        {"year": row["fiscalYear"], "period": row["period"]}
        for row in rows
        if isinstance(row, Mapping)
        and row.get("fiscalYear") is not None
        and row.get("period") is not None
    ]
