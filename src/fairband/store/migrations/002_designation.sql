-- The designation (method 0.6): price ÷ value as a REAL, which reads back as the double the engine
-- computed, and its band word. The stance columns stay and are no longer written.

ALTER TABLE snapshots ADD COLUMN price_to_value REAL;
ALTER TABLE snapshots ADD COLUMN designation TEXT;
