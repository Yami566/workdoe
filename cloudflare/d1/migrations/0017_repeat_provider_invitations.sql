CREATE TABLE IF NOT EXISTS repeat_provider_invitations (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    source_job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    source_match_request_id INTEGER REFERENCES match_requests(id) ON DELETE SET NULL,
    client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service_slug TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'bid_sent', 'declined', 'withdrawn')
    ),
    created_at TEXT NOT NULL,
    responded_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, contractor_id)
);

CREATE INDEX IF NOT EXISTS idx_repeat_provider_invitations_contractor
ON repeat_provider_invitations(contractor_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_repeat_provider_invitations_client
ON repeat_provider_invitations(client_id, status, updated_at DESC);
