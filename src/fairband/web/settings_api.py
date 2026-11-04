"""The settings routes (spec 2026-11-04 8.7): the Settings form with its values, a save and a reset.

A save applies all or none (``fairband.store.settings.write_settings``); a refused one is a 400
whose detail is ``"<name>: <rule>"``, naming the first failing setting. A reset deletes the named
rows, or every row when it names none, and never builds the policy first, so it clears a stored
row the policy no longer accepts: a name a later policy file dropped, or a value outside a new
range. While such a row is stored, every route that reads the effective policy answers 409 with
the sentence that names it (``effective``), rather than show figures under a policy nobody chose
or fail with a 500. Each answers with the form as ``GET`` serves it.

``valuedUnder`` says what the screen's figures were valued under: the policy version and settings
hash most of the screen's snapshots cite, the start of the latest full refresh that finished, and
whether a universe setting changed after that start. The screen's snapshots are those of the
latest universe's admitted companies, the ones a revalue values; a company the universe dropped
keeps its old snapshot and would otherwise outvote them. A universe change is read from the
change log, so a reset or a save back to the default counts too: it deletes the setting's row,
but the universe was built under the value it removed.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from fairband.policy import Policy
from fairband.store.companies import latest_companies
from fairband.store.refreshes import latest_full_refresh
from fairband.store.settings import (
    changes,
    effective_policy,
    overlay_changed_at,
    read_overlay,
    reset_settings,
    write_settings,
)
from fairband.store.snapshots import latest_versions
from fairband.web.policy_rows import settings_json


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


def valued_under(conn: sqlite3.Connection) -> dict[str, Any]:
    """What the screen's snapshots were valued under, and whether a save or a reset changed a
    universe setting after the latest full refresh began; before any full refresh, whether one
    ever changed."""
    versions = latest_versions(conn, _screen_symbols(conn))
    full = latest_full_refresh(conn)
    start = None if full is None else full.started_at
    universe_changed = any(
        any(entry["name"].startswith("universe.") for entry in change.changes)
        for change in changes(conn)
        if start is None or change.changed_at > start
    )
    return {
        "policyVersion": None if versions is None else versions[0],
        "settingsHash": None if versions is None else versions[1],
        "fullRefreshAt": None if start is None else start.isoformat(),
        "universeChanged": universe_changed,
    }


def _screen_symbols(conn: sqlite3.Connection) -> list[str] | None:
    """The symbols the screen shows and a revalue values: the latest universe's admitted
    companies; ``None``, every company with a snapshot, before any universe."""
    admitted = latest_companies(conn)
    if admitted or latest_companies(conn, eligible_only=False):
        return [company.symbol for company in admitted]
    return None


def add_settings_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    clock: Callable[[], datetime],
) -> None:
    """Register the three settings routes; ``policy`` is the file's, the defaults."""

    def form(conn: sqlite3.Connection) -> dict[str, Any]:
        current = effective(conn, policy)
        overlay = read_overlay(conn)
        changed_at = overlay_changed_at(conn)
        return settings_json(current, policy, overlay, changed_at, valued_under(conn))

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
