-- The user's settings and watchlists (spec 2026-11-04, 8.6 and 9.2). The settings overlay holds one
-- row per setting changed from the policy file's default; a reset deletes the row, and
-- settings_changes logs every save and reset. Each refresh and snapshot records the settings hash
-- it ran under; the rows before this migration ran under the empty overlay, whose hash is the
-- sha256 of "{}".

CREATE TABLE settings (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,          -- JSON
    changed_at TEXT NOT NULL
);

CREATE TABLE settings_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    changed_at TEXT NOT NULL,
    reason TEXT,
    changes TEXT NOT NULL         -- JSON: [{"name", "old", "new"}]
);

CREATE TABLE watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);

CREATE TABLE watchlist_entries (
    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (watchlist_id, symbol)
);

ALTER TABLE refreshes ADD COLUMN settings_hash TEXT NOT NULL
    DEFAULT '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a';
ALTER TABLE snapshots ADD COLUMN settings_hash TEXT NOT NULL
    DEFAULT '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a';
