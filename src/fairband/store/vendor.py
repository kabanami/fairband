"""Every vendor call as received: provider, endpoint, parameters, symbol, status, time, payload.

The caller scrubs secrets before a response reaches this module. ``params`` is stored as canonical
JSON (sorted keys), so a lookup matches the same parameters in any order. ``ResponseRow`` leaves
out the payload, which can be large; ``response_payload`` reads it by id.
"""

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from fairband.store._codec import dump_stamp, inserted_id, load_stamp
from fairband.store.db import transaction


@dataclass(frozen=True)
class ResponseRow:
    id: int
    provider: str
    endpoint: str
    params: dict[str, str]
    symbol: str | None
    http_status: int | None
    observed_at: datetime
    error: str | None


def record_response(
    conn: sqlite3.Connection,
    provider: str,
    endpoint: str,
    params: Mapping[str, str],
    symbol: str | None,
    http_status: int | None,
    payload: str | None,
    error: str | None,
    observed_at: datetime,
) -> int:
    """Store one call and return its id; ``http_status`` is ``None`` when no response came."""
    row = (
        provider,
        endpoint,
        _canonical(params),
        symbol,
        http_status,
        dump_stamp(observed_at),
        payload,
        error,
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO vendor_responses (provider, endpoint, params, symbol, http_status,"
            " observed_at, payload, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    return inserted_id(cursor)


def latest_response(
    conn: sqlite3.Connection,
    provider: str,
    endpoint: str,
    symbol: str | None,
    params: Mapping[str, str],
) -> ResponseRow | None:
    """The most recently observed HTTP 200 response to the same call, if any."""
    row = conn.execute(
        "SELECT id, provider, endpoint, params, symbol, http_status, observed_at, error"
        " FROM vendor_responses"
        " WHERE provider = ? AND endpoint = ? AND symbol IS ? AND params = ? AND http_status = 200"
        " ORDER BY observed_at DESC, id DESC LIMIT 1",
        (provider, endpoint, symbol, _canonical(params)),
    ).fetchone()
    if row is None:
        return None
    return ResponseRow(
        id=row["id"],
        provider=row["provider"],
        endpoint=row["endpoint"],
        params=json.loads(row["params"]),
        symbol=row["symbol"],
        http_status=row["http_status"],
        observed_at=load_stamp(row["observed_at"]),
        error=row["error"],
    )


def response_payload(conn: sqlite3.Connection, response_id: int) -> str | None:
    """The payload text of the response, or ``None`` when it has none or does not exist."""
    row = conn.execute(
        "SELECT payload FROM vendor_responses WHERE id = ?", (response_id,)
    ).fetchone()
    return None if row is None else row["payload"]


def _canonical(params: Mapping[str, str]) -> str:
    return json.dumps(dict(params), sort_keys=True)
