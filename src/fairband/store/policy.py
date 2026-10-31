"""The policy versions results were computed under: version, hash, content and first-seen time.

A version is stored once; the parsed TOML is stored as JSON with sorted keys. A version seen again
with a different hash is refused, since a policy file, once versioned, is never edited.
"""

import json
import sqlite3
from datetime import datetime

from fairband.policy import Policy
from fairband.store._codec import dump_stamp
from fairband.store.db import transaction


def record_policy(conn: sqlite3.Connection, policy: Policy, at: datetime) -> None:
    """Store the policy if its version is new; ``ValueError`` if the version has another hash."""
    content = json.dumps(policy.raw, sort_keys=True)
    with transaction(conn):
        conn.execute(
            "INSERT INTO policy_versions (version, hash, content, created_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT (version) DO NOTHING",
            (policy.version, policy.hash, content, dump_stamp(at)),
        )
        stored = conn.execute(
            "SELECT hash FROM policy_versions WHERE version = ?", (policy.version,)
        ).fetchone()
        if stored["hash"] != policy.hash:
            raise ValueError(
                f"policy {policy.version} is recorded with hash {stored['hash']}, not {policy.hash}"
            )
