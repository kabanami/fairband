"""The user's settings: the overlay of the policy file, its change log and the effective policy.

``settings`` holds one row per setting the user changed from the file's default: the name and its
value as JSON, in the form the API serves, with the time it last changed. A setting at its default
has no row. ``settings_changes`` logs each save and reset with its reason, as a list of
``{"name", "old", "new"}``, where ``None`` stands for the default.

``effective_policy`` is the policy a run or a request reads: the file's values with the overlay
applied and every range checked (``fairband.policy.settings.apply_overlay``). A row the policy no
longer accepts, a name a later file dropped or a value outside its range, raises ``ValueError``
naming the row and the way out, rather than valuing under a policy nobody chose.

``write_settings`` applies a save all or none: it takes the write lock, checks the overlay with
the changes over it, and writes only when every range and rule passes. Each value is stored in its
converted form, the form ``apply_overlay`` gives it (a float for a fraction, a whole number for a
count, symbols upper-cased), so one choice always hashes alike. A value equal to its default is
stored as no row, and a value equal to the stored one is neither written nor logged, so a save
that changes nothing never moves the settings hash or a ``changed_at``. ``reset_settings``
deletes rows by name, whether or not the name is still a setting.
"""

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fairband.policy import Policy, load_policy
from fairband.policy.settings import apply_overlay, default_of
from fairband.store._codec import dump_stamp, load_stamp
from fairband.store.db import transaction


@dataclass(frozen=True)
class ChangeRow:
    """One save or reset: each entry's ``old`` and ``new`` values, ``None`` for the default."""

    id: int
    changed_at: datetime
    reason: str | None
    changes: list[dict[str, Any]]


def read_overlay(conn: sqlite3.Connection) -> dict[str, Any]:
    """The stored settings, name to value, ordered by name."""
    rows = conn.execute("SELECT name, value FROM settings ORDER BY name")
    return {r["name"]: json.loads(r["value"]) for r in rows}


def overlay_changed_at(conn: sqlite3.Connection) -> dict[str, datetime]:
    """When each stored setting last changed, by name."""
    rows = conn.execute("SELECT name, changed_at FROM settings ORDER BY name")
    return {r["name"]: load_stamp(r["changed_at"]) for r in rows}


def effective_policy(conn: sqlite3.Connection, base: Policy | None = None) -> Policy:
    """``base`` (default: the packaged file) with the stored overlay applied and checked."""
    file_policy = load_policy() if base is None else base
    overlay = read_overlay(conn)
    try:
        return apply_overlay(file_policy, overlay)
    except ValueError as e:
        raise ValueError(f"settings: {e}; reset it on the Settings page") from e


def write_settings(
    conn: sqlite3.Connection,
    changes: Mapping[str, Any],
    reason: str | None,
    at: datetime,
    base: Policy | None = None,
) -> Policy:
    """Store the changes over the overlay and log them as one save; return the new effective
    policy. ``ValueError("<name>: <rule>")`` on the first failing setting, with nothing written."""
    file_policy = load_policy() if base is None else base
    with transaction(conn, immediate=True):
        before = read_overlay(conn)
        checked = apply_overlay(file_policy, {**before, **changes})
        after = dict(before)
        entries: list[dict[str, Any]] = []
        for name in changes:
            new = _stored(checked, name)
            if new == default_of(name, file_policy):
                new = None
            old = before.get(name)
            if new == old:
                continue
            if new is None:
                del after[name]
            else:
                after[name] = new
            entries.append({"name": name, "old": old, "new": new})
        policy = apply_overlay(file_policy, after)
        for entry in entries:
            if entry["new"] is None:
                conn.execute("DELETE FROM settings WHERE name = ?", (entry["name"],))
            else:
                conn.execute(
                    "INSERT INTO settings (name, value, changed_at) VALUES (?, ?, ?)"
                    " ON CONFLICT (name) DO UPDATE"
                    " SET value = excluded.value, changed_at = excluded.changed_at",
                    (entry["name"], _json(entry["new"]), dump_stamp(at)),
                )
        _log(conn, at, reason, entries)
    return policy


def reset_settings(conn: sqlite3.Connection, names: Sequence[str] | None, at: datetime) -> None:
    """Delete the named settings' rows (every row when ``names`` is ``None``) and log the reset.
    A name with no row is no change."""
    with transaction(conn, immediate=True):
        before = read_overlay(conn)
        gone = list(before) if names is None else [n for n in dict.fromkeys(names) if n in before]
        for name in gone:
            conn.execute("DELETE FROM settings WHERE name = ?", (name,))
        _log(conn, at, None, [{"name": n, "old": before[n], "new": None} for n in gone])


def changes(conn: sqlite3.Connection) -> list[ChangeRow]:
    """Every logged save and reset, newest first."""
    rows = conn.execute("SELECT * FROM settings_changes ORDER BY id DESC")
    return [
        ChangeRow(
            id=r["id"],
            changed_at=load_stamp(r["changed_at"]),
            reason=r["reason"],
            changes=json.loads(r["changes"]),
        )
        for r in rows
    ]


def _stored(policy: Policy, name: str) -> Any:
    """The setting's value in ``policy`` in its JSON form: tuples become lists."""
    group, _, field = name.rpartition(".")
    holder = getattr(policy, group) if group else policy
    return json.loads(_json(getattr(holder, field)))


def _log(
    conn: sqlite3.Connection, at: datetime, reason: str | None, entries: list[dict[str, Any]]
) -> None:
    """One ``settings_changes`` row for the entries; none when nothing changed."""
    if entries:
        conn.execute(
            "INSERT INTO settings_changes (changed_at, reason, changes) VALUES (?, ?, ?)",
            (dump_stamp(at), reason, _json(entries)),
        )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)
