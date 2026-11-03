-- The facts of one response by field: the statement facts backfill asks, for every stored
-- statement response, which fields its facts already hold.

CREATE INDEX facts_by_response ON facts (response_id, field);
