-- Immutable acknowledgement records for versioned service safety advisories.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS service_policy_acknowledgements (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_role TEXT NOT NULL CHECK (actor_role IN ('client', 'contractor')),
    context TEXT NOT NULL CHECK (context IN ('project-post', 'mini-bid')),
    service_slug TEXT NOT NULL REFERENCES service_types(slug),
    policy_version TEXT NOT NULL,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    match_request_id INTEGER REFERENCES match_requests(id) ON DELETE CASCADE,
    acknowledged_at TEXT NOT NULL,
    CHECK (
        (context = 'project-post' AND job_id IS NOT NULL AND match_request_id IS NULL)
        OR
        (context = 'mini-bid' AND job_id IS NOT NULL AND match_request_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_service_policy_ack_user
ON service_policy_acknowledgements(user_id, acknowledged_at DESC);

CREATE INDEX IF NOT EXISTS idx_service_policy_ack_resource
ON service_policy_acknowledgements(context, job_id, match_request_id);
