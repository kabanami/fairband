"""The FastAPI app: the screen page, the static files, the screen's JSON API, the group view, the
refresh routes (spec 6.10), the settings and watchlist routes (``settings_api``,
``watchlists_api``), the agent routes of the work inbox, the research records and the ledger
(``agents_api``), the guidance routes (``guidance_api``), the override and review routes
(``reviews_api``), the moat class's write (``moat_api``), the sensitivity reading's routes
(``sensitivity_api``), the company reads, the Methodology section read and the report routes
(``reports_api``), the company page's four reads (``company_api``), the research read
(``research_api``), the multiples history read (``multiples_api``), the band's history read
(``history_api``), the vendor pass-through route (``vendor_api``), the filing reads
(``filings_api``), the company logo's read (``logo_api``), and the policy values and growth
deciles the Methodology page cites (spec 2026-11-04 7.4). The
Agents section's settings routes (``launch_api``) read and write ``launch.json`` in the config
folder, not the ``settings`` table; its launch routes (``launch_api``) store a launch, open its
window and take its launcher's reports. The company detail carries the agents' records that the
drawer and the company page read (``research_api.agent_records``).

``create_app`` builds it over a connection factory: each API request opens its own connection
and closes it before it answers. The static files are the package's ``web/static`` directory:
the page, its script, the design system copy and the vendored React, so the page renders with
no network. The page and each static file answer ``Cache-Control: no-cache``: a browser keeps its
copy and asks at each load whether the file changed (a 304 where it did not), so it never draws
a newer server's page with an older build's script. Nothing here reads a key. The refresh routes hand the work to the ``RefreshWorker``,
whose thread calls the vendors; without one they answer 503. ``serve`` always passes one; without
an FMP key its runs refuse every kind but a revalue, and a refusal is a 400. The pass-through
route, the multiples history read and the filing reads alone call a vendor from a request: they
call FMP on FastAPI's sync-route thread through the ``Passthrough`` that ``serve`` builds with the
FMP key, paced by the one limiter the worker's runs share, and answer the stored payload scrubbed,
so no answer carries a key; without a pass-through (no FMP key) the route and the filing reads
answer 503 and the read serves the trailing series stored before, ``null`` with none.
What is bounded: four vendor calls in flight; a request that finds them all taken waits at most
ten seconds for a slot, holding its pool thread meanwhile, and past that answers 503. The logo's
read fetches a company's logo from FMP's image host with ``fetch_logo``, which ``serve`` passes;
that host takes no key, so the read needs no pass-through, and an app given no fetch reads the
stored files alone. FastAPI's own documentation routes are off; they would load their scripts
from a CDN.

The screen's rows are the latest universe's admitted companies, each with its latest snapshot,
or a placeholder row "not yet valued" before its first; a company the latest universe does not
admit has no row. The latest universe is the newest that admitted a company
(``latest_companies``), so a refresh whose screener admitted nobody leaves the screen as it was.
Before any universe exists, every company with a snapshot has its row. The group view groups the
same rows. Each row carries the ids of the watchlists the company is on, and the agents' fields
(``rows.agent_fields``) from the companies' current reviews, newest secondary valuations and latest
published reports and the snapshots those rest on: four reads at most for all the rows, whatever
their number, the fields computed for the companies that have a row.

Each request that reads a policy value reads the effective policy, the file's values with the
user's settings over them, so a changed setting shows at the next request: the aging fraction of
the rows' freshness and of the company detail, the designation edges of the groups, of the word a
row reads at its reviewed value (``rows.agent_fields``) and of the drawer. A stored setting
the policy refuses makes those routes answer 409 naming it, until it is reset (``settings_api``).

When the app starts, it marks ``interrupted`` every refresh left ``running`` by a server or a
command that stopped, and ``failed`` at the window stage every launch a server that stopped left
``opening`` (``store.launches.fail_opening``), and logs how many of each.

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
must carry ``X-Fairband-Request: 1``, else 403. So must the reads that may call a vendor, the
pass-through route (``/api/vendor/{kind}/{symbol}``), the multiples history read
(``/api/companies/{symbol}/multiples-history``), the filing reads
(``/api/companies/{symbol}/filings``, ``/filing-report`` and ``/filing-report/search``) and the
company page's reads of an earnings call and of a year of filings
(``/api/companies/{symbol}/page/investor-relations/call`` and ``/filings``): each spends a
vendor's quota and stores its answer, and an image tag or a link on any other site passes the host
check. The page's read and the MCP server's client send the header on every call. A
cross-site form cannot send that header, and a cross-origin script cannot without a CORS
preflight, which the app never answers. The logo's read (``/api/companies/{symbol}/logo``) may
fetch a file from FMP's image host and is not among them (B-203): the page reads it from an
``<img>``, which cannot send the header. It refuses a request the browser marks as another
site's (``Sec-Fetch-Site``), and its fetch sends no key, spends no quota and is bounded as
``logo_api`` says. The launch route (``POST /api/launches``, spec 2026-11-16 agent launch, 12) is
the one route that starts a program: it runs the window command of ``launch.json`` as a list of
words through the ``Opener`` that ``serve`` passes, with no shell and no word from the request,
which names a stored item's id or a test. It is the owner's alone, as is the launcher's report
(``POST /api/launches/{id}/status``): a request with the agent's principal header is a 403. Both
are writes and need the header, so a page on another site can neither launch nor report. It is
bounded: one launch in flight for an item, and 15 seconds for the window command. An app given no
opener or no port answers it 503 and starts nothing.
"""

import logging
import os
import re
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
from starlette.types import Scope

from fairband.config import Settings, utcnow
from fairband.engine.levels import moat_of
from fairband.engine.types import ValuationResult, money_of, rated
from fairband.launch.command import Opener
from fairband.launch.settings import read_launch_file
from fairband.policy import Policy
from fairband.policy.moat import MoatTable, load_moat_table
from fairband.policy.tax import TaxTable, load_tax_table
from fairband.refresh.inputs import adr_flag
from fairband.refresh.inputs_statements import brief_for
from fairband.refresh.passthrough import Passthrough
from fairband.refresh.run import KINDS
from fairband.refresh.worker import RefreshWorker
from fairband.store.companies import CompanyRow, latest_companies, latest_company
from fairband.store.launches import fail_opening
from fairband.store.moat import moat_classes, moat_row
from fairband.store.refreshes import (
    RefreshRow,
    RefreshRunning,
    latest_deciles,
    latest_refresh,
    latest_shown_refresh,
    mark_interrupted,
)
from fairband.store.reports import latest_reports
from fairband.store.research import notes_for
from fairband.store.reviews import latest_reviews
from fairband.store.secondary import latest_secondaries
from fairband.store.settings import read_overlay
from fairband.store.snapshots import (
    SnapshotRow,
    latest_snapshot,
    latest_snapshots,
    snapshot_rows,
)
from fairband.store.watchlists import memberships
from fairband.vendors.logos import LogoError, Logos
from fairband.web.agents_api import add_agent_routes
from fairband.web.company_api import add_company_page_routes
from fairband.web.filings_api import add_filing_routes
from fairband.web.guidance_api import add_guidance_routes
from fairband.web.history_api import add_history_routes
from fairband.web.launch_api import add_launch_routes, add_launch_settings_routes
from fairband.web.logo_api import add_logo_routes, logo_route
from fairband.web.moat_api import add_moat_routes, moat_json
from fairband.web.multiples_api import add_multiples_routes
from fairband.web.policy_rows import deciles_json, policy_json
from fairband.web.reports_api import add_report_routes
from fairband.web.research_api import add_research_routes, agent_records
from fairband.web.reviews_api import add_review_routes
from fairband.web.rows import (
    COLUMNS,
    GROUP_BY,
    NO_AGENT_FIELDS,
    ROW_KEYS,
    agent_fields,
    company_json,
    group_rows,
    placeholder_row,
    progress_json,
    refresh_json,
    rested_on,
    result_json,
    screen_row,
    snapshot_json,
    sort_rows,
)
from fairband.web.sensitivity_api import add_sensitivity_routes
from fairband.web.settings_api import add_settings_routes, effective
from fairband.web.vendor_api import add_vendor_routes
from fairband.web.warning_words import is_marked, warning_words
from fairband.web.watchlists_api import add_watchlist_routes

logger = logging.getLogger("fairband.web")

_STATIC = resources.files("fairband.web").joinpath("static")
# The page and its files: kept by the browser, and asked for again at each load.
_CHECK_AGAIN = {"Cache-Control": "no-cache"}
TRUSTED_HOSTS = ["127.0.0.1", "localhost"]
REQUEST_HEADER = "X-Fairband-Request"
_SAFE_METHODS = ("GET", "HEAD")
# The reads that may call a vendor (D11, B-109), as their routes match a path: no segment holds a
# slash.
_VENDOR_READS = re.compile(
    r"/api/vendor/[^/]+/[^/]+"
    r"|/api/companies/[^/]+/multiples-history"
    r"|/api/companies/[^/]+/filings"
    r"|/api/companies/[^/]+/filing-report"
    r"|/api/companies/[^/]+/filing-report/search"
    r"|/api/companies/[^/]+/page/investor-relations/call"
    r"|/api/companies/[^/]+/page/investor-relations/filings"
)
_NO_WORKER = "no refresh worker"


class _CheckedStatic(StaticFiles):
    """The static files, each answered with ``Cache-Control: no-cache``: the file, and the 304 of
    one that did not change. Without the header a browser reuses a script for a time it works out
    from the file's age, and draws an older build's script on a newer server's page."""

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers.update(_CHECK_AGAIN)
        return response


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
    passthrough: Passthrough | None = None,
    fetch_logo: Callable[[str], bytes] | None = None,
    opener: Opener | None = None,
    port: int | None = None,
    moat: MoatTable | None = None,
) -> FastAPI:
    """The app; ``policy`` is the file's, which the user's settings overlay; ``clock`` gives the
    day the validity states are judged on and the time a refresh left running is marked
    interrupted, a setting changed, a watchlist entry added and an agent route's record
    written; ``tax`` is the table a review's inputs and the company reads' statements are built
    with, the packaged one when ``None``; ``passthrough`` fetches the vendor pass-throughs, which
    answer 503 without one; ``fetch_logo`` fetches a logo's file from its address
    (``vendors.logos.fetch_logo``), and without one the logo read answers the files already in
    the data folder's ``logos`` and fetches none. ``opener`` is what opening a window reaches
    outside the server (``launch.command.Opener``): the launch route runs the window command
    through it, the Agents section's save checks a changed window command's program with its
    finder, and its read suggests the Windows Terminal line from its environment. ``port`` is the
    port the server listens on, which the window's launcher calls back on. Without an opener or a
    port the launch route answers 503 and starts nothing; without an opener the save checks no
    program and the read suggests none. ``clock`` also gives the time a launch is made, moved and
    read at. ``moat`` is the moat table the moat class's write loads in its revalue and returns
    a company to, and whose class the detail names beside the row: the packaged file when
    ``None``; ``serve`` passes the one its refreshes load, so the two read one version."""
    taxed = load_tax_table() if tax is None else tax
    table = load_moat_table() if moat is None else moat
    logos = Logos(settings.data_dir / "logos", fetch_logo or _no_fetch, clock)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with closing(conn_factory()) as conn:
            count = mark_interrupted(conn, clock())
            failed = fail_opening(conn, clock())
        logger.info("%d running refresh%s marked interrupted", count, "" if count == 1 else "es")
        logger.info("%d opening launch%s marked failed", failed, "" if failed == 1 else "es")
        yield

    app = FastAPI(
        title="Fairband", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.mount("/static", _CheckedStatic(directory=str(_STATIC)), name="static")

    @app.middleware("http")
    async def require_request_header(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        vendor_read = _VENDOR_READS.fullmatch(request.url.path) is not None
        guarded = request.method not in _SAFE_METHODS or vendor_read
        if guarded and request.headers.get(REQUEST_HEADER) != "1":
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
        return FileResponse(
            str(_STATIC.joinpath("index.html")), media_type="text/html", headers=_CHECK_AGAIN
        )

    def current(conn: sqlite3.Connection) -> Policy:
        """The effective policy: the file's values with the user's settings over them."""
        return effective(conn, policy)

    def screen_rows(today: date) -> tuple[list[dict[str, Any]], RefreshRow | None, Policy]:
        """A row per admitted company of the latest universe (see the module docstring), in
        symbol order, its freshness and its report's window judged on ``today``; the latest
        refresh's record; and the effective policy the rows were read under."""
        with closing(conn_factory()) as conn:
            read_under = current(conn)
            admitted = latest_companies(conn)
            listed = bool(admitted) or bool(latest_companies(conn, eligible_only=False))
            snapshots = {s.symbol: s for s in latest_snapshots(conn)}
            refresh = latest_refresh(conn)
            lists = memberships(conn)
            reviews, secondaries = latest_reviews(conn), latest_secondaries(conn)
            reports = latest_reports(conn)
            shown = [c.symbol for c in admitted] if listed else list(snapshots)
            records = {
                symbol: (reviews.get(symbol), secondaries.get(symbol), reports.get(symbol))
                for symbol in shown
                if symbol in snapshots
                and (symbol in reviews or symbol in secondaries or symbol in reports)
            }
            rest_on = {i for s, found in records.items() for i in rested_on(snapshots[s], *found)}
            cited = snapshot_rows(conn, rest_on)
            classes = moat_classes(conn) if records else {}
        agents = {
            symbol: agent_fields(
                snapshots[symbol], *found, cited, today, read_under, classes.get(symbol)
            )
            for symbol, found in records.items()
        }
        aging, mark_min = read_under.aging_fraction, read_under.warning_mark_min

        def valued(snapshot: SnapshotRow, company: CompanyRow | None) -> dict[str, Any]:
            watchlists = lists.get(snapshot.symbol, [])
            fields = agents.get(snapshot.symbol, NO_AGENT_FIELDS)
            return screen_row(
                snapshot,
                company,
                today,
                aging,
                watchlists,
                fields,
                mark_min=mark_min,
                policy=read_under,
            )

        def row(company: CompanyRow) -> dict[str, Any]:
            snapshot = snapshots.get(company.symbol)
            if snapshot is None:
                return placeholder_row(company, lists.get(company.symbol, []))
            return valued(snapshot, company)

        if listed:
            rows = [row(company) for company in admitted]
        else:
            rows = [valued(s, None) for s in snapshots.values()]
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
        rows, refresh, read_under = screen_rows(today)
        return {
            "rows": sort_rows(rows, sort, direction == "desc", read_under.stance_words),
            "columns": list(COLUMNS),
            "today": today.isoformat(),
            "refresh": None if refresh is None else refresh_json(refresh),
        }

    @app.get("/api/groups")
    def groups(by: str) -> dict[str, Any]:
        """The screen's rows grouped by sector, industry, phase or cap band (``group_rows``)."""
        if by not in GROUP_BY:
            raise HTTPException(400, f"by must be sector, industry, phase or cap, not {by}")
        rows, _, read_under = screen_rows(clock().date())
        return {"by": by, "groups": group_rows(rows, by, read_under.fair_band[0])}

    @app.get("/api/companies/{symbol}")
    def company(symbol: str) -> dict[str, Any]:
        """The company's latest snapshot in full, its levels, price ÷ value and word read on the
        effective policy (``rows.result_json``; spec 2026-11-23 thresholds, 5.3), with its latest
        universe row, two of the effective
        policy's values: the designation edges of the company's own moat class (the result's, else
        its row's of the moat table; none without a class), by which the drawer keeps its price ÷
        value figure inside the word's band, and ``aging_fraction``, from which a validity window reads aging
        where the screen's Freshness column does (no page draws the window since it left the drawer,
        the company page's design 11); and the agents' records that the drawer and the company page
        read (``research_api.agent_records``: ``review``, ``secondary``, ``report``, ``item``), with
        ``moat``, the moat class in force, which the drawer's head and the company page's head
        stamp (the company page's design, 7.2): the class of the company's row of the moat table,
        a refused row's too, ``None`` without a row (spec 2026-11-19 8.6); and ``moatClass``, that
        row with the class the moat table the app was given holds for the company
        (``moat_api.moat_json``), ``None`` without a row; and ``noteCount``, the count of the
        company's notes, which the Notes control draws beside its word (11.1); and the company
        brief (B-149), the latest stored profile's description, which the drawer shows cut at six
        lines and the MCP ``company`` tool carries (the company page's Overview reads its own,
        ``page_fmp``); and ``logo`` (B-203), the address of the company's logo read where the
        latest stored profile names a logo, which the heads of the drawer and the company page
        draw, ``None`` without one (``logo_api.logo_route``). And what the figures are in (spec
        2026-11-10 7.4), which the drawer's head and the Research tab name: ``currency``, the
        reporting currency the snapshot was valued or refused in (``types.money_of``: USD for a
        USD row, the code for a row refused for its currency); ``isAdr``, the ADR flag as assembly
        reads it, the latest stored profile's, else the universe row's, ``None`` with neither
        (``inputs.adr_flag``);
        ``adrRatio``, the ADR ratio the share count was read by, the whole number Fairband found
        between FMP's stored share count and the quote's (spec 2026-11-19 6.2), the result's
        ``adr_ratio`` input, ``None`` without one, an ADR whose counts agree included; neither
        line names it, since the counts cannot say which way a depositary's ratio runs;
        ``fxRate`` and ``fxDate``, the rate the value was translated at and its close's date,
        ``None`` on a row with no rate (``types.rated``). And ``launchReady``
        (spec 2026-11-16 agent launch, 9), whether launching is set up: the launch file in the
        config folder, read at each request, can be used and its window command holds a word
        (``launch.settings``); the open item's ``launch`` is read at the clock's time. And the
        mark's two fields, as a screen row has them (spec 2026-11-19 7.5; ``rows``):
        ``warnings``, the plain words of the snapshot's quality warnings in the order of its
        flags, never a review's (``warning_words``), and ``marked``, read against the counting
        review: the snapshot has a value, the review is none or has no value, and the snapshot
        carries the effective policy's ``warning_mark_min`` warnings or more (``is_marked``)."""
        now = clock()
        today = now.date()
        with closing(conn_factory()) as conn:
            snapshot = latest_snapshot(conn, symbol)
            listed = latest_company(conn, symbol)
            read_under = current(conn)
            if snapshot is None:
                raise HTTPException(404, f"no snapshot for {symbol}")
            records = agent_records(conn, snapshot, today, read_under, taxed, now)
            brief = brief_for(conn, symbol)
            logo = logo_route(conn, snapshot.symbol)
            adr = adr_flag(conn, symbol, listed)
            note_count = len(notes_for(conn, snapshot.symbol))
            held = moat_row(conn, snapshot.symbol)
            moat_class = moat_json(held, table)
        # the edges of the company's own class: the result's, else its row's of the moat table
        own_class = moat_of(snapshot.result) or (None if held is None else held.moat)
        edges = None if own_class is None else list(read_under.edges_for(own_class))
        warnings = warning_words(snapshot.result.flags)
        review = records["review"]
        reviewed = None if review is None else review["value"]
        mark_min = read_under.warning_mark_min
        return {
            "company": None if listed is None else company_json(listed),
            "brief": brief,
            "logo": logo,
            **_money_json(snapshot.result, adr),
            "snapshot": snapshot_json(snapshot),
            "result": result_json(snapshot, read_under),
            "warnings": warnings,
            "marked": is_marked(snapshot.value, reviewed, warnings, mark_min),
            "today": today.isoformat(),
            "designationEdges": edges,
            "agingFraction": read_under.aging_fraction,
            **records,
            "moatClass": moat_class,
            "noteCount": note_count,
            "launchReady": read_launch_file(settings.config_dir).ready,
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
        """The running refresh's progress and kind; with none running, the last refresh's record,
        the record the page's status line describes (``shown``: the last one, passing over a
        finished revalue of named companies, which a moat write records) and the error the last
        run raised, if any."""
        progress = None if worker is None else worker.status()
        with closing(conn_factory()) as conn:
            last = latest_refresh(conn)
            shown = latest_shown_refresh(conn)
        if progress is not None:
            kind = last.kind if last is not None and last.id == progress.refresh_id else None
            return {"refresh": progress_json(progress, kind)}
        return {
            "refresh": None,
            "last": None if last is None else refresh_json(last),
            "shown": None if shown is None else refresh_json(shown),
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
    add_agent_routes(app, conn_factory, clock, settings.config_dir)
    add_guidance_routes(app, conn_factory, policy, taxed, clock)
    add_review_routes(app, conn_factory, policy, taxed, clock)
    add_moat_routes(app, conn_factory, policy, taxed, table, clock)
    add_sensitivity_routes(app, conn_factory, policy, taxed, clock)
    add_report_routes(app, conn_factory, policy, taxed, clock)
    add_company_page_routes(app, conn_factory, policy, taxed, clock, passthrough)
    add_research_routes(app, conn_factory)
    add_history_routes(app, conn_factory)
    add_multiples_routes(app, conn_factory, passthrough)
    add_vendor_routes(app, passthrough)
    add_filing_routes(app, passthrough, clock)
    add_logo_routes(app, conn_factory, logos)
    add_launch_settings_routes(app, settings.config_dir, opener)
    add_launch_routes(app, conn_factory, settings.config_dir, opener, port, clock)
    return app


def _no_fetch(url: str) -> bytes:
    """The logo fetch of an app given none: it fetches nothing."""
    raise LogoError("this app fetches no logo")


def _money_json(result: ValuationResult, adr: bool | None) -> dict[str, Any]:
    """What the snapshot's figures are in (``company``): the reporting currency, the ADR flag
    ``adr``, the ADR ratio input and, for a row that carries a rate (``types.rated``), the rate
    and its date; a row refused for its currency names the code with neither, since the 1.0
    ``money_of`` gives it is no rate."""
    rate, currency = money_of(result)
    with_rate = rated(result)
    return {
        "currency": currency,
        "isAdr": adr,
        "adrRatio": next((i.value for i in result.inputs if i.name == "adr_ratio"), None),
        "fxRate": rate if with_rate else None,
        "fxDate": result.intermediates.get("fx_date") if with_rate else None,
    }


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
