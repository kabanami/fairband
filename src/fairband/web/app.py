"""The FastAPI app: the screen page, the static files and the screen's JSON API (spec 6.10).

``create_app`` builds it over a connection factory: each API request opens its own connection
and closes it before it answers. The static files are the package's ``web/static`` directory:
the page, its script, the design system copy and the vendored React, so the page renders with
no network. Nothing here reads a key or calls a vendor. FastAPI's own documentation routes are
off; they would load their scripts from a CDN.
"""

import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime
from importlib import resources
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fairband.config import Settings, utcnow
from fairband.engine.types import result_to_json
from fairband.policy import Policy
from fairband.store.companies import latest_company
from fairband.store.refreshes import latest_refresh
from fairband.store.snapshots import latest_snapshot, latest_snapshots
from fairband.web.rows import (
    COLUMNS,
    ROW_KEYS,
    company_json,
    refresh_json,
    screen_row,
    snapshot_json,
    sort_rows,
)

_STATIC = resources.files("fairband.web").joinpath("static")


def create_app(
    settings: Settings,
    policy: Policy,
    conn_factory: Callable[[], sqlite3.Connection],
    worker: object | None = None,  # the refresh worker; unused until the refresh routes exist
    clock: Callable[[], datetime] = utcnow,
) -> FastAPI:
    """The app; ``clock`` gives the day the validity states are judged on."""
    app = FastAPI(title="Fairband", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    @app.get("/")
    def page() -> FileResponse:
        return FileResponse(str(_STATIC.joinpath("index.html")), media_type="text/html")

    @app.get("/api/screen")
    def screen(
        sort: str = "ticker", direction: Annotated[str, Query(alias="dir")] = "asc"
    ) -> dict[str, Any]:
        """Every company's latest snapshot as a row, ordered by ``sort``; rows without a value
        for it come last."""
        if sort not in ROW_KEYS:
            raise HTTPException(400, f"unknown sort column: {sort}")
        if direction not in ("asc", "desc"):
            raise HTTPException(400, f"dir must be asc or desc, not {direction}")
        today = clock().date()
        with closing(conn_factory()) as conn:
            rows = [
                screen_row(s, latest_company(conn, s.symbol), today, policy.aging_fraction)
                for s in latest_snapshots(conn)
            ]
            refresh = latest_refresh(conn)
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

    return app
