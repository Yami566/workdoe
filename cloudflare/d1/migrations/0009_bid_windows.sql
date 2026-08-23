ALTER TABLE jobs
ADD COLUMN bid_limit INTEGER NOT NULL DEFAULT 4 CHECK (bid_limit BETWEEN 1 AND 8);

ALTER TABLE jobs
ADD COLUMN bidding_closes_at TEXT;

UPDATE jobs
SET bidding_closes_at = CASE
    WHEN status = 'open'
        THEN strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '+7 days')
    ELSE strftime('%Y-%m-%dT%H:%M:%SZ', created_at, '+7 days')
END
WHERE bidding_closes_at IS NULL OR bidding_closes_at = '';

CREATE INDEX IF NOT EXISTS idx_jobs_bidding_window
ON jobs(status, bidding_closes_at);
