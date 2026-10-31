"""Store fixtures: a migrated database and makers for the rows other rows cite."""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fairband.store.db import connect, migrate
from fairband.store.refreshes import create_refresh, finish_refresh
from fairband.store.vendor import record_response

_AT = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(connect(tmp_path / "f.db")) as conn:
        migrate(conn)
        yield conn


@pytest.fixture
def new_refresh(conn: sqlite3.Connection) -> Callable[[], int]:
    """Makes a finished refresh and returns its id."""

    def make() -> int:
        refresh_id = create_refresh(
            conn, "scoped", ["AAPL"], "fairband-policy-v1", "fairband-mechanical/0.1", _AT
        )
        finish_refresh(conn, refresh_id, "done", _AT)
        return refresh_id

    return make


@pytest.fixture
def new_response(conn: sqlite3.Connection) -> Callable[[], int]:
    """Records a successful vendor response and returns its id."""

    def make() -> int:
        return record_response(
            conn, "fmp", "income-statement", {"symbol": "AAPL"}, "AAPL", 200, "[]", None, _AT
        )

    return make
