import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from fairband.policy import load_policy
from fairband.store.policy import record_policy

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
T1 = datetime(2026, 11, 2, 9, 30, tzinfo=UTC)


def _stored(conn: sqlite3.Connection) -> list[tuple[str, ...]]:
    rows = conn.execute("select version, hash, content, created_at from policy_versions")
    return [tuple(r) for r in rows]


def test_record_policy_inserts_once(conn: sqlite3.Connection) -> None:
    policy = load_policy()
    record_policy(conn, policy, T0)
    assert not conn.in_transaction
    expected = [
        (
            policy.version,
            policy.hash,
            json.dumps(policy.raw, sort_keys=True),
            "2026-11-01T09:30:00+00:00",
        )
    ]
    assert _stored(conn) == expected
    record_policy(conn, policy, T1)
    assert _stored(conn) == expected


def test_record_policy_rejects_changed_hash(conn: sqlite3.Connection) -> None:
    policy = load_policy()
    record_policy(conn, policy, T0)
    before = _stored(conn)
    with pytest.raises(ValueError, match=policy.version):
        record_policy(conn, replace(policy, hash="0" * 64), T1)
    assert not conn.in_transaction
    assert _stored(conn) == before
