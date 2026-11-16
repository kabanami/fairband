-- A window opened from the research button, and what its launcher reported (spec 2026-11-16).
CREATE TABLE launches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER REFERENCES work_items(id),  -- NULL: a test from Settings
    agent TEXT NOT NULL,                        -- 'claude'
    state TEXT NOT NULL,                        -- opening, opened, started, ended, failed
    stage TEXT,                                 -- of a failure: window, agent
    detail TEXT,                                -- a failure's sentence
    exit_code INTEGER,                          -- of an agent that ended
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX launches_item ON launches (item_id, id);
