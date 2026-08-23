ALTER TABLE jobs ADD COLUMN close_reason TEXT CHECK (
    close_reason IS NULL OR close_reason IN (
        'workdoe-match', 'hired-elsewhere', 'plans-changed',
        'no-qualified-bid', 'scope-changed', 'duplicate', 'other'
    )
);

ALTER TABLE jobs ADD COLUMN close_note TEXT NOT NULL DEFAULT '';

ALTER TABLE jobs ADD COLUMN closed_at TEXT;

UPDATE jobs
SET close_reason = CASE
        WHEN EXISTS (
            SELECT 1
            FROM match_requests
            WHERE match_requests.job_id = jobs.id
              AND match_requests.status = 'approved'
        ) THEN 'workdoe-match'
        ELSE 'other'
    END,
    close_note = COALESCE(close_note, ''),
    closed_at = COALESCE(
        NULLIF(closed_at, ''),
        NULLIF(updated_at, ''),
        NULLIF(created_at, ''),
        strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    )
WHERE status = 'closed'
  AND (close_reason IS NULL OR close_reason = '');

CREATE TABLE IF NOT EXISTS job_lead_feedback (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason_code TEXT NOT NULL CHECK (
        reason_code IN (
            'insufficient-detail', 'wrong-service', 'outside-service-area',
            'client-unresponsive', 'already-hired', 'duplicate',
            'authorization-concern', 'suspicious', 'other'
        )
    ),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, contractor_id)
);

CREATE INDEX IF NOT EXISTS idx_job_lead_feedback_reason
ON job_lead_feedback(reason_code, created_at);
