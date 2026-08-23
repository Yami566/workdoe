-- Durable duplicate-submit protection for core marketplace creates.
-- Stores only a SHA-256 request-key hash and generic resource references.
CREATE TABLE IF NOT EXISTS idempotency_requests (
    id INTEGER PRIMARY KEY,
    actor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (length(action) BETWEEN 1 AND 80),
    key_hash TEXT NOT NULL CHECK (length(key_hash) = 64),
    resource_type TEXT NOT NULL CHECK (
        resource_type IN ('job', 'message', 'report', 'job_photo', 'contractor_photo')
    ),
    resource_id INTEGER,
    status TEXT NOT NULL DEFAULT 'processing' CHECK (
        status IN ('processing', 'completed')
    ),
    created_at TEXT NOT NULL,
    completed_at TEXT,
    expires_at TEXT NOT NULL,
    UNIQUE(actor_id, action, key_hash)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_requests_expiry
ON idempotency_requests(status, expires_at);
