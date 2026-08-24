ALTER TABLE jobs ADD COLUMN budget_min INTEGER;
ALTER TABLE jobs ADD COLUMN budget_max INTEGER;

CREATE TABLE IF NOT EXISTS job_drafts (
    id INTEGER PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    description TEXT NOT NULL,
    desired_date TEXT DEFAULT '',
    budget_min INTEGER,
    budget_max INTEGER,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_drafts_expires
ON job_drafts(expires_at, consumed_at);
