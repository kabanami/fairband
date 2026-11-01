"""The FastAPI app: the screen page, the static files, the screen's JSON API and the refresh routes
(spec 6.10).

``create_app`` builds it over a connection factory: each API request opens its own connection
and closes it before it answers. The static files are the package's ``web/static`` directory:
the page, its script, the design system copy and the vendored React, so the page renders with
no network. Nothing here reads a key or calls a vendor: the refresh routes hand the work to the
``RefreshWorker``, whose thread calls the vendors; without one (no FMP key) they answer 503.
FastAPI's own documentation routes are off; they would load their scripts from a CDN.

The screen's rows are the latest universe's admitted companies, each with its latest snapshot,
or a placeholder row "not yet valued" before its first; a company the latest universe does not
admit has no row. Before any universe exists, every company with a snapshot has its row.

When the app starts, it marks ``interrupted`` every refresh left ``running`` by a server or a
command that stopped, and logs how many.

D11, for a server bound to 127.0.0.1: ``TrustedHostMiddleware`` answers 400 to a request whose
``Host`` is neither ``127.0.0.1`` nor ``localhost`` (any port), so a page on another name that
resolves here (DNS rebinding) cannot read the API; and a request other than ``GET`` or ``HEAD``
must carry ``X-Fairband-Request: 1``, else 403. A cross-site form cannot send that header, and a
cross-origin script cannot without a CORS preflight, which the app never answers.
"""

import json
import logging
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, closing
from datetime import datetime
from importlib import resources
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from fairband.config import Settings, utcnow
from fairband.engine.types import result_to_json
from fairband.policy import Policy
from fairband.refresh.run import KINDS
from fairband.refresh.worker import RefreshWorker
from fairband.store.companies import CompanyRow, latest_companies, latest_company
from fairband.store.refreshes import RefreshRunning, latest_refresh, mark_interrupted
from fairband.store.snapshots import latest_snapshot, latest_snapshots
from fairband.web.rows import (
    COLUMNS,
    ROW_KEYS,
    company_json,
    placeholder_row,
    progress_json,
    refresh_json,
    screen_row,
    snapshot_json,
    sort_rows,
)

logger = logging.getLogger("fairband.web")

_STATIC = resources.files("fairband.web").joinpath("static")
TRUSTED_HOSTS = ["127.0.0.1", "localhost"]
REQUEST_HEADER = "X-Fairband-Request"
_SAFE_METHODS = ("GET", "HEAD")
_NO_WORKER = "no refresh worker: start the server with the vendor keys"


class RefreshRequest(BaseModel):
    kind: str
    symbols: list[str] | None = None


def create_app(
    settings: Settings,
    policy: Policy,
    conn_factory: Callable[[], sqlite3.Connection],
    worker: RefreshWorker | None = None,
    clock: Callable[[], datetime] = utcnow,
) -> FastAPI:
    """The app; ``clock`` gives the day the validity states are judged on and the time a
    refresh left running is marked interrupted."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with closing(conn_factory()) as conn:
            count = mark_interrupted(conn, clock())
        logger.info("%d running refresh%s marked interrupted", count, "" if count == 1 else "es")
        yield

    app = FastAPI(
        title="Fairband", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    @app.middleware("http")
    async def require_request_header(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in _SAFE_METHODS and request.headers.get(REQUEST_HEADER) != "1":
            return JSONResponse({"detail": f"missing {REQUEST_HEADER} header"}, status_code=403)
        return await call_next(request)

    # Added last, so it runs first: an untrusted host is refused before anything else.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        """A request the routes' types refuse is a 400 like every other bad request, its detail
        one line: ``<field>: <what is wrong>`` for each error."""
        return JSONResponse({"detail": _validation_detail(exc)}, status_code=400)

    @app.get("/")
    def page() -> FileResponse:
        return FileResponse(str(_STATIC.joinpath("index.html")), media_type="text/html")

    @app.get("/api/screen")
    def screen(
        sort: str = "ticker", direction: Annotated[str, Query(alias="dir")] = "asc"
    ) -> dict[str, Any]:
        """A row per admitted company of the latest universe (see the module docstring), ordered
        by ``sort``; rows without a value for it come last."""
        if sort not in ROW_KEYS:
            raise HTTPException(400, f"unknown sort column: {sort}")
        if direction not in ("asc", "desc"):
            raise HTTPException(400, f"dir must be asc or desc, not {direction}")
        today = clock().date()
        with closing(conn_factory()) as conn:
            universe = latest_companies(conn, eligible_only=False)
            snapshots = {s.symbol: s for s in latest_snapshots(conn)}
            refresh = latest_refresh(conn)

        def row(company: CompanyRow) -> dict[str, Any]:
            snapshot = snapshots.get(company.symbol)
            if snapshot is None:
                return placeholder_row(company)
            return screen_row(snapshot, company, today, policy.aging_fraction)

        if universe:
            rows = [row(company) for company in universe if company.eligible]
        else:
            rows = [screen_row(s, None, today, policy.aging_fraction) for s in snapshots.values()]
        return {
            "rows": sort_rows(rows, sort, descending=direction == "desc"),
            "columns": list(COLUMNS),
            "today": today.isoformat(),
            "refresh": None if refresh is None else refresh_json(refresh),
        }

    @app.get("/api/companies/{symbol}")
    def company(symbol: str) -> dict[str, Any]:
        """The company's latest snapshot in full, with its latest universe row."""
        today = clock().date()
        with closing(conn_factory()) as conn:
            snapshot = latest_snapshot(conn, symbol)
            listed = latest_company(conn, symbol)
        if snapshot is None:
            raise HTTPException(404, f"no snapshot for {symbol}")
        return {
            "company": None if listed is None else company_json(listed),
            "snapshot": snapshot_json(snapshot),
            "result": json.loads(result_to_json(snapshot.result)),
            "today": today.isoformat(),
        }

    @app.post("/api/refresh", response_model=None)
    def start_refresh(body: RefreshRequest) -> dict[str, int] | JSONResponse:
        """Start a refresh on the worker: its id, or 409 with the running one's."""
        if worker is None:
            raise HTTPException(503, _NO_WORKER)
        if body.kind not in KINDS:
            raise HTTPException(400, f"unknown refresh kind: {body.kind}")
        try:
            refresh_id = worker.start(body.kind, body.symbols)
        except RefreshRunning as exc:
            return JSONResponse({"running": exc.refresh_id}, status_code=409)
        except (ValueError, NotImplementedError) as exc:
            raise HTTPException(400, str(exc)) from None
        return {"refreshId": refresh_id}

    @app.get("/api/refresh/current")
    def refresh_current() -> dict[str, Any]:
        """The running refresh's progress; with none running, the last refresh's record and the
        error its run raised, if any."""
        progress = None if worker is None else worker.status()
        if progress is not None:
            return {"refresh": progress_json(progress)}
        with closing(conn_factory()) as conn:
            last = latest_refresh(conn)
        return {
            "refresh": None,
            "last": None if last is None else refresh_json(last),
            "error": None if worker is None else worker.last_error,
        }

    @app.post("/api/refresh/cancel")
    def refresh_cancel() -> dict[str, bool]:
        """Ask the running refresh to stop after the companies in flight."""
        if worker is not None:
            worker.cancel()
        return {"cancelled": True}

    return app


def _validation_detail(exc: RequestValidationError) -> str:
    """Each error as ``<where>: <message>``, joined by ``; ``. ``<where>`` is the field's path
    without its ``body`` or ``query`` root (``symbols.0``), or the root itself when the error is
    about the whole of it: a missing body, or one that is not JSON (whose path ends in the
    parser's position, not a field)."""
    parts = []
    for error in exc.errors():
        loc = error["loc"]
        field = "" if error["type"] == "json_invalid" else ".".join(str(p) for p in loc[1:])
        parts.append(f"{field or loc[0]}: {error['msg']}")
    return "; ".join(parts)
