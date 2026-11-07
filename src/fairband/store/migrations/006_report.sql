-- The report's records (spec 2026-11-06 Tier 2, as amended 2026-11-07: sections 9, 11, 12, 13.7
-- and 13.8): a judgment as a record without its debate text, the secondary valuation's standard
-- form, the multiples log, the sensitivity readings and the guidance records. The conventions
-- are 005's: numbers are repr text, a tuple or a dict is JSON text, dates and timestamps are the
-- store codec's text, a write names its writer (principal, actor, client), and a record cites
-- another by id alone, with no foreign key.

-- A judgment is the record of a decision and the override it produced: the bull and the bear
-- case are the report's own section now. Each judgment keeps its decision and its override.
-- DROP COLUMN needs SQLite 3.35.
ALTER TABLE judgments DROP COLUMN bull;
ALTER TABLE judgments DROP COLUMN bear;

-- The secondary valuation's two forms: a plan 1 record is the parts form. The drivers form
-- stores its drivers and its projection table; every record of fairband-secondary/2 its grid.
ALTER TABLE secondary_valuations ADD COLUMN form TEXT NOT NULL DEFAULT 'parts';
ALTER TABLE secondary_valuations ADD COLUMN drivers TEXT;     -- JSON, or NULL on the parts form
ALTER TABLE secondary_valuations ADD COLUMN projection TEXT;  -- JSON, or NULL on the parts form
ALTER TABLE secondary_valuations ADD COLUMN grid TEXT;        -- JSON, or NULL on a /1 record

-- The forward P/E's history (13.7): a row a company a day, written at every price refresh and
-- every snapshot. The UNIQUE constraint is the log's index on (symbol, day).
CREATE TABLE multiples_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    day TEXT NOT NULL,
    price TEXT NOT NULL,
    pe_reported TEXT,
    pe_clean TEXT,
    pe_forward TEXT,
    snapshot_id INTEGER,
    refresh_id INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE (symbol, day)
);

-- A sensitivity reading of the route (13.8): the engine's value a share at each pair of two
-- overridable inputs, on a snapshot under the review's applied overrides. Nothing is overridden.
CREATE TABLE sensitivities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL,
    review_id INTEGER,
    created_at TEXT NOT NULL,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    row_tag TEXT NOT NULL,
    col_tag TEXT NOT NULL,
    row_values TEXT NOT NULL,     -- JSON: the row input's values, a number or a word each
    col_values TEXT NOT NULL,     -- JSON: the column input's values, as the row's
    cells TEXT NOT NULL,          -- JSON: [[value a share or null]], a row for each row value
    current_row INTEGER,          -- the pair in force, both or neither: NULL when no pair is it
    current_col INTEGER,
    policy_version TEXT NOT NULL,
    settings_hash TEXT NOT NULL
);

CREATE INDEX sensitivities_by_symbol ON sensitivities (symbol, snapshot_id);

-- A guidance record (9): a figure the company gave on a call for a future period, its midpoint
-- and its step computed by the server. A newer record for the same metric and period supersedes
-- the older; every record stays.
CREATE TABLE guidance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    metric TEXT NOT NULL,
    period TEXT NOT NULL,
    low TEXT NOT NULL,
    high TEXT NOT NULL,
    midpoint TEXT NOT NULL,
    step TEXT,                    -- a fiscal-year revenue or EPS figure's growth from its base year
    basis TEXT NOT NULL,
    as_of TEXT NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    created_at TEXT NOT NULL,
    superseded_by INTEGER
);

CREATE INDEX guidance_by_symbol ON guidance (symbol);
