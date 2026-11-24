-- The forward P/E on the analysts' EPS as they state it (method 1.10, 5.9 and 16.7; the founder's
-- decision of 2026-11-24).
--
-- Until method 1.10 the multiples log's forward P/E was the price over the anchor's raw NTM EPS
-- less its stock-pay adjustment. From 1.10 it is the price over the raw figure. This puts the rows
-- on file on the raw figure too, so every point of a company's series is on one basis.
--
-- A row's snapshot holds what its figure was made from: the anchor's raw EPS and its adjustment,
-- and the forward P/E the row logged. Such a row reads the logged figure x (raw - adjustment) /
-- raw. The ratio has no unit, so a price logged in US dollars beside a snapshot in another
-- currency needs no rate.
--
-- First the rows whose snapshot cannot say what the raw figure was lose their forward P/E; their
-- price and their trailing multiples stay. These are a revenue-growth row, whose snapshot records
-- no anchor; a row whose snapshot holds no forward P/E, or another one, the logged figure being an
-- earlier write's of the same day; a row whose raw figure is at or below zero, a loss that has no
-- forward P/E; and a row with no snapshot. The company's next valued day logs the figure on the
-- raw EPS. A result that is not JSON reads as one that holds nothing.
UPDATE multiples_log
SET pe_forward = NULL
WHERE pe_forward IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM snapshots s
    WHERE s.id = multiples_log.snapshot_id
      AND json_extract(
            CASE WHEN json_valid(s.result) THEN s.result END,
            '$.intermediates.anchor.ntm_eps_raw') > 0
      AND abs(
            json_extract(
              CASE WHEN json_valid(s.result) THEN s.result END,
              '$.intermediates.multiples.pe_forward')
            - CAST(multiples_log.pe_forward AS REAL))
          <= 1e-9 * abs(CAST(multiples_log.pe_forward AS REAL)));

-- Then every row left with a forward P/E has a snapshot that made it. One whose adjustment is nil
-- already holds the price over the raw figure and keeps its text. The others are restated, written
-- with the 17 significant digits that read back as the same number.
UPDATE multiples_log
SET pe_forward = (
    SELECT printf(
        '%!.17g',
        CAST(multiples_log.pe_forward AS REAL)
        * (json_extract(s.result, '$.intermediates.anchor.ntm_eps_raw')
           - json_extract(s.result, '$.intermediates.anchor.sbc_adjustment_per_share'))
        / json_extract(s.result, '$.intermediates.anchor.ntm_eps_raw'))
    FROM snapshots s
    WHERE s.id = multiples_log.snapshot_id)
WHERE pe_forward IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM snapshots s
    WHERE s.id = multiples_log.snapshot_id
      AND json_extract(s.result, '$.intermediates.anchor.sbc_adjustment_per_share') <> 0);
