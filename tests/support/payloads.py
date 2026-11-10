"""FMP payloads stored as a fetch stores them: the response whole, with the rows its normalizer
gives, for tests that need statements, consensus, closes or peers in the store without running a
refresh. The params are ``{"symbol": <symbol>}``, the key the closes and the peers are read back
by."""

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from fairband.store.facts import insert_facts
from fairband.store.observations import insert_observations
from fairband.store.vendor import record_response
from fairband.vendors.normalize_fmp import (
    as_reported_balance_facts,
    estimate_observations,
    statement_facts,
)

_STATEMENTS = frozenset(
    {"income-annual", "income-quarter", "balance-annual", "cashflow-annual", "cashflow-quarter"}
)
_WHOLE = frozenset({"price-history", "peers", "profile"})  # stored whole, giving no rows


def store_payloads(
    conn: sqlite3.Connection, symbol: str, payloads: Mapping[str, Any], at: datetime
) -> None:
    """Store each payload as ``symbol``'s FMP response to its endpoint, observed ``at``."""
    for endpoint, payload in payloads.items():
        response = record_response(
            conn, "fmp", endpoint, {"symbol": symbol}, symbol, 200, json.dumps(payload), None, at
        )
        if endpoint in _STATEMENTS:
            insert_facts(conn, statement_facts(payload, symbol, endpoint, response, at, at))
        elif endpoint == "balance-asreported-annual":
            insert_facts(conn, as_reported_balance_facts(payload, symbol, response, at, at))
        elif endpoint in ("estimates-annual", "estimates-quarter"):
            period = "annual" if endpoint == "estimates-annual" else "quarter"
            rows = estimate_observations(payload, symbol, period, response, at, at)
            insert_observations(conn, rows)
        elif endpoint not in _WHOLE:
            raise ValueError(f"no normalizer for endpoint {endpoint}")
