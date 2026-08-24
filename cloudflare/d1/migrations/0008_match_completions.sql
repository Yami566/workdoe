CREATE TABLE IF NOT EXISTS match_completions (
    match_request_id INTEGER PRIMARY KEY
        REFERENCES match_requests(id) ON DELETE CASCADE,
    client_confirmed_at TEXT,
    contractor_confirmed_at TEXT,
    verified_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_match_completions_verified
ON match_completions(verified_at, updated_at);
