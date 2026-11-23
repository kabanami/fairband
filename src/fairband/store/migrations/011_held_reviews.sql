-- The held reviewed value (spec 2026-11-23 held reviewed value, 5.1, 5.10 and 5.12).
--
-- A review is one of three kinds. A made review is written by a deliberate act: an override's
-- write or drop, a moat class's write, or Review again. A held review is a made one that a refresh
-- carried onto a newer snapshot, and names it in made_id. A reading is what the review gives on a
-- newer snapshot, computed by a refresh; it names the made review it reads again, when there is
-- one. A row written before this migration with none of the marks below reads as a reading.
ALTER TABLE reviews ADD COLUMN kind TEXT NOT NULL DEFAULT 'reading';
ALTER TABLE reviews ADD COLUMN made_id INTEGER;

-- The log tells the kinds apart; a row written before this migration has none.
ALTER TABLE review_log ADD COLUMN kind TEXT;

-- One row for a company that holds a review: its made review, and the facts a refresh stores for
-- its state (spec 5.3). A company with no row has no review.
CREATE TABLE held_reviews (
    symbol TEXT PRIMARY KEY,
    review_id INTEGER NOT NULL,          -- the made review
    made_at TEXT NOT NULL,
    read_again_at TEXT,                  -- the first valuing refresh after it was made
    newer_period TEXT,                   -- reason 1: the newer trailing period's end
    dropped TEXT NOT NULL DEFAULT '[]',  -- reason 2: JSON [{id, tag, reason, at}]
    reading_value TEXT,                  -- reason 3: the newest good reading's value, as repr
    reading_refusal TEXT,                -- or its refusal
    reading_at TEXT,
    early_at TEXT                        -- the day a refresh first found a reason
);

-- An expiry item stands for one held record (spec 5.10): the made review or the secondary
-- valuation it was posted for. NULL on an item posted for a snapshot's window.
ALTER TABLE work_items ADD COLUMN expiry_review_id INTEGER;
ALTER TABLE work_items ADD COLUMN expiry_secondary_id INTEGER;

-- The reviews made so far (spec 5.12): one with no refresh, which an override's write or drop
-- made; one a published report cites; and one a moat class's write made, the review of the
-- revalue that names the company alone and started within a minute after the write's ledger row,
-- or of the snapshot the company's row of the moat table names.
UPDATE reviews
SET kind = 'made'
WHERE refresh_id IS NULL
   OR id IN (SELECT review_id FROM reports WHERE review_id IS NOT NULL)
   OR snapshot_id IN (
        SELECT m.snapshot_id FROM moat_classes m
        WHERE m.symbol = reviews.symbol AND m.snapshot_id IS NOT NULL)
   OR refresh_id IN (
        SELECT f.id
        FROM refreshes f
        JOIN ledger l ON l.kind = 'moat' AND l.symbol = reviews.symbol
        WHERE f.kind = 'revalue'
          AND f.symbols = json_array(l.symbol)
          AND julianday(f.started_at) >= julianday(l.at)
          AND (julianday(f.started_at) - julianday(l.at)) * 86400.0 < 60.0);

-- A company with an applied override and no made review holds its newest review, so none is left
-- without one.
UPDATE reviews
SET kind = 'made'
WHERE id IN (
    SELECT MAX(id)
    FROM reviews
    WHERE symbol IN (SELECT symbol FROM overrides WHERE state = 'applied')
    GROUP BY symbol
    HAVING SUM(kind = 'made') = 0);

-- Each company with an applied override holds its newest made review. A company whose last
-- override was dropped before this migration has no review, as before it.
INSERT INTO held_reviews (symbol, review_id, made_at)
SELECT symbol, id, created_at
FROM reviews
WHERE id IN (
    SELECT MAX(id)
    FROM reviews
    WHERE kind = 'made'
      AND symbol IN (SELECT symbol FROM overrides WHERE state = 'applied')
    GROUP BY symbol);
