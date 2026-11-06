"""The FastAPI app: the screen page, the static files, the screen's JSON API, the group view, the
refresh routes (spec 6.10), the settings and watchlist routes (``settings_api``,
``watchlists_api``), the agent routes of the work inbox, the research records and the ledger
(``agents_api``), the override and review routes (``reviews_api``), the company reads and the
Methodology section read (``reports_api``), and the policy values and growth deciles the
Methodology page cites (spec 2026-11-04 7.4).

``create_app`` builds it over a connection factory: each API request opens its own connection
and closes it before it answers. The static files are the package's ``web/static`` directory:
the page, its script, the design system copy and the vendored React, so the page renders with
no network. Nothing here reads a key or calls a vendor: the refresh routes hand the work to the
``RefreshWorker``, whose thread calls the vendors; without one they answer 503. ``serve`` always
passes one; without an FMP key its runs refuse every kind but a revalue, and a refusal is a 400.
FastAPI's own documentation routes are off; they would load their scripts from a CDN.

The screen's rows are the latest universe's admitted companies, each with its latest snapshot,
or a placeholder row "not yet valued" before its first; a company the latest universe does not
admit has no row. The latest universe is the newest that admitted a company
(``latest_companies``), so a refresh whose screener admitted nobody leaves the screen as it was.
Before any universe exists, every company with a snapshot has its row. The group view groups the
same rows. Each row carries the ids of the watchlists the company is on.

Each request that reads a policy value reads the effective policy, the file's values with the
user's settings over them, so a changed setting shows at the next request: the aging fraction of
the rows' freshness and the drawer's validity window, the designation edges of the groups and the
drawer. A stored setting the policy refuses makes those routes answer 409 naming it, until it is
reset (``settings_api``).

When the app starts, it marks ``interrupted`` every refresh left ``running`` by a server or a
command that stopped, and logs how many.

A write names its writer (spec 2026-11-06 Tier 2, section 7; ``identity``): an agent sends
``X-Fairband-Principal: agent`` with ``X-Fairband-Actor``, the model identifier it runs as, and
``X-Fairband-Client``, its client's name and version; a request without the principal header is
the owner's. An agent's write without an actor is a 400, "identify first: the model identifier
you run as", and any other principal a 400. The agent routes record each write in the ledger
under its writer; the system's own writes, such as an expiry item posted when the inbox is read,
are the principal ``system``, which no request can name. The override and review routes
(``reviews_api``) take an agent's override or drop, an agent's write alone, and recompute the
company's review over its applied overrides.

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
from datetime import date, datetime
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
from fairband.policy.tax import TaxTable, load_tax_table
from fairband.refresh.run import KINDS
from fairband.refresh.worker import RefreshWorker
from fairband.store.companies import CompanyRow, latest_companies, latest_company
from fairband.store.refreshes import (
    RefreshRow,
    RefreshRunning,
    latest_deciles,
    latest_refresh,
    mark_interrupted,
)
from fairband.store.settings import read_overlay
from fairband.store.snapshots import latest_snapshot, latest_snapshots
from fairband.store.watchlists import memberships
from fairband.web.agents_api import add_agent_routes
from fairband.web.policy_rows import deciles_json, policy_json
from fairband.web.reports_api import add_report_routes
from fairband.web.reviews_api import add_review_routes
from fairband.web.rows import (
    COLUMNS,
    GROUP_BY,
    ROW_KEYS,
    company_json,
    group_rows,
    placeholder_row,
    progress_json,
    refresh_json,
    screen_row,
    snapshot_json,
    sort_rows,
)
from fairband.web.settings_api import add_settings_routes, effective
from fairband.web.watchlists_api import add_watchlist_routes

logger = logging.getLogger("fairband.web")

_STATIC = resources.files("fairband.web").joinpath("static")
TRUSTED_HOSTS = ["127.0.0.1", "localhost"]
REQUEST_HEADER = "X-Fairband-Request"
_SAFE_METHODS = ("GET", "HEAD")
_NO_WORKER = "no refresh worker"


class RefreshRequest(BaseModel):
    kind: str
    symbols: list[str] | None = None


def create_app(
    settings: Settings,
    policy: Policy,
    conn_factory: Callable[[], sqlite3.Connection],
    worker: RefreshWorker | None = None,
    clock: Callable[[], datetime] = utcnow,
    tax: TaxTable | None = None,
) -> FastAPI:
    """The app; ``policy`` is the file's, which the user's settings overlay; ``clock`` gives the
    day the validity states are judged on and the time a refresh left running is marked
    interrupted, a setting changed, a watchlist entry added and an agent route's record
    written; ``tax`` is the table a review's inputs and the company reads' statements are built
    with, the packaged one when ``None``."""

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

    def current(conn: sqlite3.Connection) -> Policy:
        """The effective policy: the file's values with the user's settings over them."""
        return effective(conn, policy)

    def screen_rows(today: date) -> tuple[list[dict[str, Any]], RefreshRow | None, Policy]:
        """A row per admitted company of the latest universe (see the module docstring), in
        symbol order, its freshness judged on ``today``; the latest refresh's record; and the
        effective policy the rows were read under."""
        with closing(conn_factory()) as conn:
            read_under = current(conn)
            admitted = latest_companies(conn)
            listed = bool(admitted) or bool(latest_companies(conn, eligible_only=False))
            snapshots = {s.symbol: s for s in latest_snapshots(conn)}
            refresh = latest_refresh(conn)
            lists = memberships(conn)
        aging = read_under.aging_fraction

        def row(company: CompanyRow) -> dict[str, Any]:
            snapshot = snapshots.get(company.symbol)
            watchlists = lists.get(company.symbol, [])
            if snapshot is None:
                return placeholder_row(company, watchlists)
            return screen_row(snapshot, company, today, aging, watchlists)

        if listed:
            rows = [row(company) for company in admitted]
        else:
            rows = [
                screen_row(s, None, today, aging, lists.get(s.symbol, []))
                for s in snapshots.values()
            ]
        return rows, refresh, read_under

    @app.get("/api/screen")
    def screen(
        sort: str = "ticker", direction: Annotated[str, Query(alias="dir")] = "asc"
    ) -> dict[str, Any]:
        """The screen's rows, ordered by ``sort``; rows without a value for it come last."""
        if sort not in ROW_KEYS:
            raise HTTPException(400, f"unknown sort column: {sort}")
        if direction not in ("asc", "desc"):
            raise HTTPException(400, f"dir must be asc or desc, not {direction}")
        today = clock().date()
        rows, refresh, _ = screen_rows(today)
        return {
            "rows": sort_rows(rows, sort, descending=direction == "desc"),
            "columns": list(COLUMNS),
            "today": today.isoformat(),
            "refresh": None if refresh is None else refresh_json(refresh),
        }

    @app.get("/api/groups")
    def groups(by: str) -> dict[str, Any]:
        """The screen's rows grouped by sector, phase or cap band (``group_rows``)."""
        if by not in GROUP_BY:
            raise HTTPException(400, f"by must be sector, phase or cap, not {by}")
        rows, _, read_under = screen_rows(clock().date())
        return {"by": by, "groups": group_rows(rows, by, read_under.designation_edges)}

    @app.get("/api/companies/{symbol}")
    def company(symbol: str) -> dict[str, Any]:
        """The company's latest snapshot in full, with its latest universe row and two of the
        effective policy's values: the designation edges, by which the drawer keeps its price ÷
        value figure inside the word's band, and ``aging_fraction``, by which its validity window
        reads aging where the screen's Freshness column does."""
        today = clock().date()
        with closing(conn_factory()) as conn:
            snapshot = latest_snapshot(conn, symbol)
            listed = latest_company(conn, symbol)
            read_under = current(conn)
        if snapshot is None:
            raise HTTPException(404, f"no snapshot for {symbol}")
        return {
            "company": None if listed is None else company_json(listed),
            "snapshot": snapshot_json(snapshot),
            "result": json.loads(result_to_json(snapshot.result)),
            "today": today.isoformat(),
            "designationEdges": list(read_under.designation_edges),
            "agingFraction": read_under.aging_fraction,
        }

    @app.get("/api/policy")
    def policy_values() -> dict[str, Any]:
        """The effective policy's values the Methodology page cites (``policy_json``)."""
        with closing(conn_factory()) as conn:
            read_under = current(conn)
            overlay = read_overlay(conn)
        return policy_json(read_under, policy, overlay)

    @app.get("/api/deciles")
    def deciles() -> dict[str, Any]:
        """The latest full refresh's revenue-growth decile edges and the growth words' deciles."""
        with closing(conn_factory()) as conn:
            found = latest_deciles(conn)
        if found is None:
            raise HTTPException(404, "no deciles yet")
        return deciles_json(found)

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
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return {"refreshId": refresh_id}

    @app.get("/api/refresh/current")
    def refresh_current() -> dict[str, Any]:
        """The running refresh's progress and kind; with none running, the last refresh's record
        and the error its run raised, if any."""
        progress = None if worker is None else worker.status()
        with closing(conn_factory()) as conn:
            last = latest_refresh(conn)
        if progress is not None:
            kind = last.kind if last is not None and last.id == progress.refresh_id else None
            return {"refresh": progress_json(progress, kind)}
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

    add_settings_routes(app, conn_factory, policy, clock)
    add_watchlist_routes(app, conn_factory, clock)
    add_agent_routes(app, conn_factory, clock)
    taxed = load_tax_table() if tax is None else tax
    add_review_routes(app, conn_factory, policy, taxed, clock)
    add_report_routes(app, conn_factory, policy, taxed, clock)
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
