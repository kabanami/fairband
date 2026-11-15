-- The agents' tools and cites (spec 2026-11-15 8.1, 9.1): a finding, a guidance record and a kill
-- criterion may name the currency of a money figure, and a kill criterion may hold one threshold
-- the author chose, with its unit. Every column is empty on a record made before, so it reads as
-- it was: a null currency is the company's reporting currency, and a criterion with no threshold
-- is words alone.
ALTER TABLE findings ADD COLUMN currency TEXT;       -- NULL: the company's reporting currency
ALTER TABLE guidance ADD COLUMN currency TEXT;       -- NULL: the company's reporting currency
ALTER TABLE kill_criteria ADD COLUMN threshold TEXT; -- a number the author chose, or NULL
ALTER TABLE kill_criteria ADD COLUMN unit TEXT;      -- the threshold's unit; with it or NULL
ALTER TABLE kill_criteria ADD COLUMN currency TEXT;  -- NULL: the company's reporting currency
