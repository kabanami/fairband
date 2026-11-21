-- Fairband's moat table (spec 2026-11-19 8.3): one row a company, the class in force. A row is the
-- packaged file's, the owner's or an agent's; a refresh reads the file into the table and never
-- touches the owner's or an agent's row (8.4). The history of changes is the ledger's.
CREATE TABLE moat_classes (
    symbol TEXT PRIMARY KEY,
    class TEXT NOT NULL,          -- Wide, Narrow, None
    source TEXT NOT NULL,         -- file, owner, agent
    file_version TEXT,            -- a file row: the table's version; else NULL
    judged_on TEXT NOT NULL,      -- the entry's date, or the day of an owner's or agent's write
    previous TEXT,                -- a local change: the class in force before it, NULL if none
    reason TEXT,                  -- an agent's, required; an owner's, optional; a file row's NULL
    evidence TEXT,                -- JSON [{kind, ref, note}], an agent's; else NULL
    principal TEXT NOT NULL,      -- system for a file row; owner; agent
    actor TEXT,
    client TEXT,
    at TEXT NOT NULL,             -- when the row was written
    snapshot_id INTEGER           -- a local change: the snapshot its revalue wrote
);

-- The agents' verdicts so far (spec 8.3; section 5, point 1): each applied moat.class override
-- becomes its agent's row, its new value the class and its old value the class before it, judged
-- on the override's UTC day, with its reason, evidence, actor, client and time, and no snapshot.
-- The override is then dropped. No row is made from a report's verdict in words, and the move
-- writes no ledger row.
INSERT INTO moat_classes (symbol, class, source, file_version, judged_on, previous, reason,
                          evidence, principal, actor, client, at, snapshot_id)
SELECT symbol, json_extract(new, '$'), 'agent', NULL, substr(at, 1, 10), json_extract(old, '$'),
       reason, evidence, 'agent', actor, client, at, NULL
FROM overrides
WHERE tag = 'moat.class' AND state = 'applied';

UPDATE overrides
SET state = 'dropped',
    drop_reason = 'moved to the moat table',
    dropped_at = strftime('%Y-%m-%dT%H:%M:%f', 'now') || '+00:00'
WHERE tag = 'moat.class' AND state = 'applied';
