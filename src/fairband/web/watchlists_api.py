"""The watchlist routes (spec 2026-11-04 9.3).

``GET /api/watchlists`` gives every list by name, ignoring case, with its symbols. A write answers
with the list it changed (a create with 201), a delete with the id it deleted, and a membership
write with the company's lists. A name in use is a 409, a missing list a 404, and a bad name or
symbol a 400. Every write needs the request header, as every write of the API does.
"""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from fairband.policy.settings import exchange_symbol
from fairband.store.watchlists import (
    NameInUse,
    WatchlistRow,
    add_symbol,
    create_watchlist,
    delete_watchlist,
    get_watchlist,
    list_watchlists,
    memberships,
    remove_symbol,
    rename_watchlist,
    set_memberships,
)


class WatchlistName(BaseModel):
    name: str


class Memberships(BaseModel):
    ids: list[int]


def watchlist_json(watchlist: WatchlistRow) -> dict[str, Any]:
    return {
        "id": watchlist.id,
        "name": watchlist.name,
        "createdAt": watchlist.created_at.isoformat(),
        "count": len(watchlist.entries),
        "symbols": [
            {"symbol": e.symbol, "addedAt": e.added_at.isoformat()} for e in watchlist.entries
        ],
    }


@contextmanager
def _refusals() -> Iterator[None]:
    """The store's refusals as answers: a name in use 409, a missing list 404, a bad name or
    symbol 400."""
    try:
        yield
    except NameInUse as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except KeyError as exc:
        raise HTTPException(404, f"no watchlist {exc.args[0]}") from None


def add_watchlist_routes(
    app: FastAPI, conn_factory: Callable[[], sqlite3.Connection], clock: Callable[[], datetime]
) -> None:
    """Register the watchlist routes."""

    @app.get("/api/watchlists")
    def watchlists() -> list[dict[str, Any]]:
        with closing(conn_factory()) as conn:
            return [watchlist_json(w) for w in list_watchlists(conn)]

    @app.post("/api/watchlists", status_code=201)
    def create(payload: WatchlistName) -> dict[str, Any]:
        with closing(conn_factory()) as conn, _refusals():
            watchlist_id = create_watchlist(conn, payload.name, clock())
            return watchlist_json(get_watchlist(conn, watchlist_id))

    @app.patch("/api/watchlists/{watchlist_id}")
    def rename(watchlist_id: int, payload: WatchlistName) -> dict[str, Any]:
        with closing(conn_factory()) as conn, _refusals():
            rename_watchlist(conn, watchlist_id, payload.name)
            return watchlist_json(get_watchlist(conn, watchlist_id))

    @app.delete("/api/watchlists/{watchlist_id}")
    def delete(watchlist_id: int) -> dict[str, int]:
        with closing(conn_factory()) as conn, _refusals():
            delete_watchlist(conn, watchlist_id)
        return {"deleted": watchlist_id}

    @app.put("/api/watchlists/memberships/{symbol}")
    def set_lists(symbol: str, payload: Memberships) -> dict[str, Any]:
        """Put the company on exactly the lists ``ids``, in one write; for the mark's popup."""
        with closing(conn_factory()) as conn, _refusals():
            set_memberships(conn, symbol, payload.ids, clock())
            stored = exchange_symbol(symbol)
            return {"symbol": stored, "watchlists": memberships(conn).get(stored, [])}

    @app.put("/api/watchlists/{watchlist_id}/symbols/{symbol}")
    def add(watchlist_id: int, symbol: str) -> dict[str, Any]:
        """Put the symbol on the list; a symbol already on it keeps its first date."""
        with closing(conn_factory()) as conn, _refusals():
            add_symbol(conn, watchlist_id, symbol, clock())
            return watchlist_json(get_watchlist(conn, watchlist_id))

    @app.delete("/api/watchlists/{watchlist_id}/symbols/{symbol}")
    def remove(watchlist_id: int, symbol: str) -> dict[str, Any]:
        with closing(conn_factory()) as conn, _refusals():
            remove_symbol(conn, watchlist_id, symbol)
            return watchlist_json(get_watchlist(conn, watchlist_id))
