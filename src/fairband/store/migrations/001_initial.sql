-- The initial schema. Rows are appended, never deleted; numbers are decimal text.

CREATE TABLE schema_versions (
    version INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE policy_versions (
    version TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE refreshes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    symbols TEXT,
    status TEXT NOT NULL,
    stage TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    policy_version TEXT NOT NULL,
    method_version TEXT NOT NULL,
    calibration TEXT,
    message TEXT
);

CREATE TABLE refresh_items (
    refresh_id INTEGER NOT NULL REFERENCES refreshes(id),
    symbol TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (refresh_id, symbol)
);

CREATE TABLE deciles (
    refresh_id INTEGER PRIMARY KEY REFERENCES refreshes(id),
    growth_edges TEXT NOT NULL,
    margin_slope_edges TEXT NOT NULL,
    n_growth INTEGER NOT NULL,
    n_margin INTEGER NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE companies (
    symbol TEXT NOT NULL,
    refresh_id INTEGER NOT NULL REFERENCES refreshes(id),
    name TEXT,
    exchange TEXT,
    sector TEXT,
    industry TEXT,
    country TEXT,
    currency TEXT,
    is_adr INTEGER NOT NULL,
    cap_band TEXT,
    market_cap TEXT,
    eligible INTEGER NOT NULL,
    exclusion_reason TEXT,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (symbol, refresh_id)
);

CREATE TABLE vendor_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    params TEXT NOT NULL,
    symbol TEXT,
    http_status INTEGER,
    observed_at TEXT NOT NULL,
    payload TEXT,
    error TEXT
);

CREATE INDEX vendor_responses_lookup
    ON vendor_responses (provider, endpoint, symbol, observed_at);

CREATE TABLE facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    dataset TEXT NOT NULL,
    period_end TEXT NOT NULL,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    field TEXT NOT NULL,
    value TEXT,
    unit TEXT,
    currency TEXT,
    kind TEXT NOT NULL,
    estimate_method TEXT,
    missing_reason TEXT,
    as_of TEXT,
    observed_at TEXT NOT NULL,
    entered_at TEXT NOT NULL,
    response_id INTEGER NOT NULL REFERENCES vendor_responses(id)
);

CREATE INDEX facts_lookup ON facts (symbol, dataset, period_end, field);

CREATE TABLE observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    dataset TEXT NOT NULL,
    period TEXT,
    field TEXT NOT NULL,
    value TEXT,
    unit TEXT,
    as_of TEXT,
    observed_at TEXT NOT NULL,
    entered_at TEXT NOT NULL,
    response_id INTEGER NOT NULL REFERENCES vendor_responses(id)
);

CREATE INDEX observations_lookup ON observations (symbol, dataset, period, field);

CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    refresh_id INTEGER NOT NULL REFERENCES refreshes(id),
    deciles_refresh_id INTEGER,
    created_at TEXT NOT NULL,
    phase TEXT,
    route TEXT,
    value TEXT,
    buy_level TEXT,
    fair_low TEXT,
    fair_high TEXT,
    trim_level TEXT,
    price TEXT NOT NULL,
    stance5 TEXT,
    stance3 TEXT,
    price_date TEXT NOT NULL,
    data_date TEXT NOT NULL,
    valid_until TEXT NOT NULL,
    flags TEXT NOT NULL,
    refusal TEXT,
    policy_version TEXT NOT NULL,
    method_version TEXT NOT NULL,
    result TEXT NOT NULL
);

CREATE INDEX snapshots_latest ON snapshots (symbol, id);
