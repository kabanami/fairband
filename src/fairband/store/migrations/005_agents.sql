-- The agents' side (spec 2026-11-06 Tier 2, sections 7 to 13 and 17): the ledger, the work
-- inbox, the research records, the overrides, the reviews and their log, the secondary
-- valuations, the derivations, the reports and their judgments. One table per record, its
-- columns the record's fields. Numbers are repr text and price ÷ value a REAL, as on the
-- snapshots; dates and timestamps are the store codec's text; a tuple or a dict is JSON text.
-- A write names its writer: principal (owner, agent or system), actor (an agent's model
-- identifier) and client (its client's name and version). The records cite one another, and a
-- ledger row the record it points to, by id alone, with no foreign key: the store modules check
-- what they cite.

CREATE TABLE ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    kind TEXT NOT NULL,
    symbol TEXT,
    ref_table TEXT NOT NULL,
    ref_id INTEGER NOT NULL,
    snapshot_id INTEGER,
    work_item_id INTEGER,
    summary TEXT NOT NULL
);

CREATE INDEX ledger_by_symbol ON ledger (symbol, id);

CREATE TABLE work_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    mode TEXT NOT NULL,
    note TEXT NOT NULL,
    snapshot_id INTEGER,
    origin TEXT NOT NULL,
    posted_by TEXT NOT NULL,      -- the poster's principal
    posted_actor TEXT,
    posted_client TEXT,
    posted_at TEXT NOT NULL,
    state TEXT NOT NULL,
    claimed_by TEXT,              -- the claiming agent's model identifier
    claimed_at TEXT,
    report_id INTEGER,
    reason TEXT,
    finished_at TEXT,
    expiry_valid_until TEXT
);

CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    text TEXT NOT NULL,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    at TEXT NOT NULL,
    override_id INTEGER
);

CREATE TABLE findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    as_of TEXT NOT NULL,
    text TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    source_note TEXT,
    value TEXT,
    unit TEXT,
    period TEXT,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    at TEXT NOT NULL
);

CREATE TABLE kill_criteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    text TEXT NOT NULL,
    state TEXT NOT NULL,
    report_id INTEGER,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    at TEXT NOT NULL,
    state_reason TEXT,
    state_at TEXT
);

CREATE TABLE news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    headline TEXT NOT NULL,
    source TEXT NOT NULL,
    text TEXT NOT NULL,
    kill_criterion_id INTEGER,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    at TEXT NOT NULL
);

CREATE TABLE overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    tag TEXT NOT NULL,
    old TEXT,                     -- JSON: a number or a word, as is new and corrected_value
    new TEXT NOT NULL,
    unit TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence TEXT NOT NULL,       -- JSON: [{"kind", "ref", "note"}]
    lifetime TEXT NOT NULL,
    period TEXT,
    corrected_value TEXT,
    snapshot_id INTEGER NOT NULL,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    at TEXT NOT NULL,
    state TEXT NOT NULL,
    message TEXT NOT NULL,
    review_id INTEGER,
    drop_reason TEXT,
    dropped_at TEXT
);

CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL,
    refresh_id INTEGER,
    created_at TEXT NOT NULL,
    value TEXT,
    buy_level TEXT,
    fair_low TEXT,
    fair_high TEXT,
    trim_level TEXT,
    price_to_value REAL,
    designation TEXT,
    refusal TEXT,
    mechanical_value TEXT,
    bridge TEXT NOT NULL,         -- JSON: the bridge's lines
    override_ids TEXT NOT NULL,   -- JSON: [id]
    policy_version TEXT NOT NULL,
    method_version TEXT NOT NULL,
    review_method TEXT NOT NULL,
    settings_hash TEXT NOT NULL,
    deciles_refresh_id INTEGER,
    result TEXT NOT NULL          -- the result JSON, as snapshots.result
);

CREATE INDEX reviews_latest ON reviews (symbol, id);

CREATE TABLE review_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    refresh_id INTEGER,
    snapshot_id INTEGER NOT NULL,
    review_id INTEGER NOT NULL,
    mechanical_phase TEXT,
    mechanical_value TEXT,
    reviewed_phase TEXT,
    reviewed_value TEXT,
    secondary_value TEXT,
    price TEXT,
    designation TEXT,
    stance TEXT
);

CREATE INDEX review_log_by_symbol ON review_log (symbol, id);

CREATE TABLE secondary_valuations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    parts TEXT NOT NULL,          -- JSON: the parts, each with its present values
    firm_value TEXT NOT NULL,
    debt TEXT NOT NULL,
    cash TEXT NOT NULL,
    shares TEXT NOT NULL,
    equity TEXT NOT NULL,
    value_per_share TEXT NOT NULL,
    buy_level TEXT,
    fair_low TEXT,
    fair_high TEXT,
    trim_level TEXT,
    price_to_value REAL,
    designation TEXT,
    reason TEXT NOT NULL,
    evidence TEXT NOT NULL,       -- JSON: [{"kind", "ref", "note"}]
    debt_source TEXT NOT NULL,
    cash_source TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    settings_hash TEXT NOT NULL,
    deciles_refresh_id INTEGER,
    secondary_method TEXT NOT NULL
);

CREATE TABLE derivations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    operation TEXT NOT NULL,
    a TEXT NOT NULL,              -- a ref, as is b
    b TEXT NOT NULL,
    years INTEGER,
    value TEXT,
    unit TEXT,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    at TEXT NOT NULL
);

CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    revision INTEGER NOT NULL,
    mode TEXT NOT NULL,
    stance TEXT NOT NULL,
    sections TEXT NOT NULL,       -- JSON: [{"heading", "parts"}]
    reuses_full_report_of INTEGER,
    snapshot_id INTEGER NOT NULL,
    review_id INTEGER,
    secondary_id INTEGER,
    work_item_id INTEGER,
    principal TEXT NOT NULL,
    actor TEXT,
    client TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (symbol, revision)
);

CREATE TABLE judgments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    judgment TEXT NOT NULL,
    bull TEXT NOT NULL,
    bear TEXT NOT NULL,
    decision TEXT NOT NULL,
    override_id INTEGER
);
