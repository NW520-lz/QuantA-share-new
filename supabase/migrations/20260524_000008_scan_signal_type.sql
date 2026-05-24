ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS signal_type VARCHAR(32);
CREATE INDEX IF NOT EXISTS idx_scan_results_signal_type ON scan_results (signal_type) WHERE signal_type IS NOT NULL;
