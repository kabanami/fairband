"""The report tests' fixtures: the packaged policy and a migrated database holding the refresh
tests' synthetic company, ACME (``refresh/synthetic.py``): twelve fiscal years of statements, 2014
to 2025, of which assembly keeps the last eleven, and five quarters, stored as a fetch stores
them, and its universe row. The refresh's ``env_valued`` fixture belongs to the refresh tests'
directory; storing the same payloads through the same normalizers gives the same statements
without a refresh."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from refresh.synthetic import NOW, add_company, bodies
from support.payloads import store_payloads

from fairband.policy import Policy, load_policy
from fairband.store.db import connect, migrate


@pytest.fixture
def policy() -> Policy:
    return load_policy()


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(connect(tmp_path / "f.db")) as conn:
        migrate(conn)
        statements = {e: p for e, p in bodies().items() if e != "earnings"}
        store_payloads(conn, "ACME", statements, NOW)
        add_company(conn)
        yield conn
