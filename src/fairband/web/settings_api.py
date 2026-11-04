"""The settings routes (spec 2026-11-04 8.7): the Settings form with its values, a save and a reset.

A save applies all or none (``fairband.store.settings.write_settings``); a refused one is a 400
whose detail is ``"<name>: <rule>"``, naming the first failing setting. A reset deletes the named
rows, or every row when it names none, and never builds the policy first, so it clears a stored
row the policy no longer accepts: a name a later policy file dropped, or a value outside a new
range. While such a row is stored, every route that reads the effective policy answers 409 with
the sentence that names it (``effective``), rather than show figures under a policy nobody chose
or fail with a 500. Each answers with the form as ``GET`` serves it.

``valuedUnder`` says what the screen's figures were valued under: the policy version and settings
hash most of the newest snapshots cite, the start of the latest full refresh that finished, and
whether a universe setting changed after that start (the overlay's rows only: a reset leaves no
row to compare).
"""

import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from fairband.policy import Policy
from fairband.policy.settings import SETTINGS
from fairband.store.refreshes import latest_full_refresh
from fairband.store.settings import (
    effective_policy,
    overlay_changed_at,
    read_overlay,
    reset_settings,
    write_settings,
)
from fairband.store.snapshots import latest_versions
from fairband.web.policy_rows import settings_json

_UNIVERSE = frozenset(s.name for s in SETTINGS if s.group == "universe")


class SettingsPut(BaseModel):
    changes: dict[str, Any]
    reason: str | None = None


class SettingsReset(BaseModel):
    names: list[str] | None = None


def effective(conn: sqlite3.Connection, base: Policy) -> Policy:
    """The effective policy over ``base``; a stored setting it refuses is a 409 naming the row."""
    try:
        return effective_policy(conn, base)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


def valued_under(conn: sqlite3.Connection, changed_at: Mapping[str, datetime]) -> dict[str, Any]:
    """What the newest snapshots were valued under, and whether a universe setting changed after
    the latest full refresh began; before any full refresh, whether one changed at all."""
    versions = latest_versions(conn)
    full = latest_full_refresh(conn)
    start = None if full is None else full.started_at
    universe = [at for name, at in changed_at.items() if name in _UNIVERSE]
    return {
        "policyVersion": None if versions is None else versions[0],
        "settingsHash": None if versions is None else versions[1],
        "fullRefreshAt": None if start is None else start.isoformat(),
        "universeChanged": any(start is None or at > start for at in universe),
    }


def add_settings_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    clock: Callable[[], datetime],
) -> None:
    """Register the three settings routes; ``policy`` is the file's, the defaults."""

    def form(conn: sqlite3.Connection) -> dict[str, Any]:
        current = effective(conn, policy)
        changed_at = overlay_changed_at(conn)
        overlay = read_overlay(conn)
        return settings_json(current, policy, overlay, changed_at, valued_under(conn, changed_at))

    @app.get("/api/settings")
    def get_settings() -> dict[str, Any]:
        with closing(conn_factory()) as conn:
            return form(conn)

    @app.put("/api/settings")
    def put_settings(payload: SettingsPut) -> dict[str, Any]:
        """Apply the changes, all or none, with the reason (a blank one is none)."""
        reason = (payload.reason or "").strip() or None
        with closing(conn_factory()) as conn:
            try:
                write_settings(conn, payload.changes, reason, clock(), policy)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None
            return form(conn)

    @app.post("/api/settings/reset")
    def reset(payload: SettingsReset | None = None) -> dict[str, Any]:
        """Reset the named settings to their defaults; with no names, every setting."""
        names = None if payload is None else payload.names
        with closing(conn_factory()) as conn:
            reset_settings(conn, names, clock())
            return form(conn)
