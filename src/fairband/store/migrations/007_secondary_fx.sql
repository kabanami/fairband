-- Foreign filers (spec 2026-11-10 7.6): a secondary valuation runs in the company's reporting
-- currency, its totals in that currency and its value a share and its levels in US dollars at its
-- snapshot's rate, which the record stores, units of the currency per USD. A USD row's rate is 1,
-- so every record made before reads as it was. A REAL, as price ÷ value is, so the rate reads back
-- as the double the snapshot holds.
ALTER TABLE secondary_valuations ADD COLUMN fx_rate REAL NOT NULL DEFAULT 1.0;
