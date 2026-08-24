CREATE TABLE IF NOT EXISTS contractor_proposal_templates (
    id INTEGER PRIMARY KEY,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL COLLATE NOCASE CHECK (length(name) BETWEEN 1 AND 60),
    source_match_request_id INTEGER REFERENCES match_requests(id) ON DELETE SET NULL,
    scope_note TEXT NOT NULL,
    timeline TEXT NOT NULL,
    experience TEXT NOT NULL,
    questions TEXT NOT NULL DEFAULT '',
    availability TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(contractor_id, name)
);

CREATE INDEX IF NOT EXISTS idx_contractor_proposal_templates_owner
ON contractor_proposal_templates(contractor_id, updated_at DESC);
