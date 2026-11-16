"""The company logo's read (B-203).

``GET /api/companies/{symbol}/logo`` answers the company's logo, a PNG: the file of the address
the latest stored profile names (``inputs_statements.logo_for``: FMP's image host alone, and no
logo where FMP sends its placeholder), kept in the data folder's ``logos`` and fetched at the
first request (``vendors.logos``: a file of ninety days or older is fetched again, and kept where
that fetch fails). A company without such an address, one whose first fetch failed and a symbol
the store holds no profile for are a 404, "no logo for <symbol>"; a failed first fetch stores
nothing, and the read asks FMP again ten minutes later. A name that is not a symbol is a 400. The
detail read's ``logo`` (``logo_route``) names this route where the profile names a logo, so the page
asks for no file it cannot have.

The route may call FMP and asks for no ``X-Fairband-Request`` header (``app``, D11): the page
reads it from an ``<img>``, which cannot send one. It reads what the browser says of the request
instead: a ``Sec-Fetch-Site`` of ``cross-site``, an image tag on another site, or ``same-site``,
one on another port of this host, is a 403 before anything is read, "the logo is read from
Fairband's own page"; the page's own image says ``same-origin``, an address typed in the browser
``none``, and a client that is no browser sends no such header. What a browser too old to send
it could be made to do is bounded: the fetch sends no key and spends no quota, its address is one
a stored profile names on FMP's image host, and for each symbol the store fetches at most once
in ninety days, once a day where the fetch of an old file fails and once in ten minutes where
the fetch of a missing file fails, each file at most ``logos.MAX_BYTES``. The answer says
``nosniff`` and ``private, max-age=86400``: the browser keeps the file a day, and reads the body as
an image alone.

The route is a sync one: FastAPI runs it on its thread pool, where a fetch waits on FMP's host.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from fairband.policy.settings import exchange_symbol
from fairband.refresh.inputs_statements import logo_for
from fairband.vendors.logos import Logos

_HEADERS = {"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"}
_OTHER_SITES = ("cross-site", "same-site")  # Sec-Fetch-Site of a request from another origin


def logo_route(conn: sqlite3.Connection, symbol: str) -> str | None:
    """The address of ``symbol``'s logo read, for the page's ``<img>``; ``None`` where the
    latest stored profile names no logo."""
    return None if logo_for(conn, symbol) is None else f"/api/companies/{symbol}/logo"


def add_logo_routes(
    app: FastAPI, conn_factory: Callable[[], sqlite3.Connection], logos: Logos
) -> None:
    """Register the logo read over the files of ``logos``."""

    @app.get("/api/companies/{symbol}/logo")
    def logo(symbol: str, request: Request) -> FileResponse:
        if request.headers.get("Sec-Fetch-Site") in _OTHER_SITES:
            raise HTTPException(403, "the logo is read from Fairband's own page")
        try:
            symbol = exchange_symbol(symbol)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        with closing(conn_factory()) as conn:
            url = logo_for(conn, symbol)
        path = None if url is None else logos.file(symbol, url)
        if path is None:
            raise HTTPException(404, f"no logo for {symbol}")
        return FileResponse(path, media_type="image/png", headers=_HEADERS)
