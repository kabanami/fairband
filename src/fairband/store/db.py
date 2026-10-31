"""The SQLite connection and the numbered migrations.

``connect`` opens the database in WAL mode with foreign keys enforced and full sync, and returns
rows as ``sqlite3.Row``. It keeps Python's default deferred transactions: the record modules wrap
each write call in ``with conn:``, so the call commits, or rolls back, as one transaction.

``migrate`` applies the packaged ``NNN_name.sql`` files not yet recorded in ``schema_versions``, in
filename order; each file commits together with its ``schema_versions`` row, or not at all. Before
applying anything it checks the sha256 of every applied file against the packaged file and refuses
with ``ValueError`` on a mismatch: a migration, once applied, is never edited.
"""

import hashlib
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from fairband.config import utcnow

_MIGRATIONS: Traversable = resources.files("fairband.store").joinpath("migrations")
_MIGRATION_NAME = re.compile(r"(\d{3})_.+\.sql")


@dataclass(frozen=True)
class _Migration:
    version: int
    filename: str
    sql: str
    checksum: str


def connect(path: Path) -> sqlite3.Connection:
    """Open (creating if needed) the database at ``path`` and its parent directories."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level="DEFERRED")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def applied_versions(conn: sqlite3.Connection) -> list[int]:
    """The recorded migration versions, ascending; ``[]`` before the first migration."""
    if not _has_schema_versions(conn):
        return []
    return [int(row[0]) for row in conn.execute("SELECT version FROM schema_versions ORDER BY 1")]


def migrate(conn: sqlite3.Connection, *, clock: Callable[[], datetime] = utcnow) -> list[str]:
    """Apply the pending migrations in order; return the filenames applied."""
    packaged = _packaged_migrations()
    by_filename = {m.filename: m for m in packaged}
    applied: set[str] = set()
    if _has_schema_versions(conn):
        for row in conn.execute("SELECT filename, checksum FROM schema_versions ORDER BY version"):
            filename, checksum = str(row[0]), str(row[1])
            migration = by_filename.get(filename)
            if migration is None:
                raise ValueError(f"migration {filename} is applied but not in the package")
            if migration.checksum != checksum:
                raise ValueError(f"migration {filename} changed after it was applied")
            applied.add(filename)
    done: list[str] = []
    for migration in packaged:
        if migration.filename not in applied:
            _apply(conn, migration, clock().isoformat())
            done.append(migration.filename)
    return done


def _apply(conn: sqlite3.Connection, migration: _Migration, applied_at: str) -> None:
    """Run one file and record it in one transaction. ``executescript`` commits any open
    transaction before it runs, so the script opens its own and the commit is explicit."""
    try:
        conn.executescript(f"BEGIN;\n{migration.sql}")
        conn.execute(
            "INSERT INTO schema_versions (version, filename, checksum, applied_at)"
            " VALUES (?, ?, ?, ?)",
            (migration.version, migration.filename, migration.checksum, applied_at),
        )
        conn.commit()
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise


def _packaged_migrations() -> list[_Migration]:
    """The ``NNN_name.sql`` files shipped in the package, sorted by filename."""
    found: list[_Migration] = []
    for entry in _MIGRATIONS.iterdir():
        match = _MIGRATION_NAME.fullmatch(entry.name)
        if match is None or not entry.is_file():
            continue
        data = entry.read_bytes()
        found.append(
            _Migration(
                version=int(match[1]),
                filename=entry.name,
                sql=data.decode("utf-8"),
                checksum=hashlib.sha256(data).hexdigest(),
            )
        )
    return sorted(found, key=lambda m: m.filename)


def _has_schema_versions(conn: sqlite3.Connection) -> bool:
    query = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_versions'"
    return conn.execute(query).fetchone() is not None
