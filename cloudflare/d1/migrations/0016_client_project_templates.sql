CREATE TABLE IF NOT EXISTS client_project_templates (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL COLLATE NOCASE,
    source_job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    service_group_slug TEXT,
    service_slug TEXT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    project_setting TEXT NOT NULL DEFAULT '',
    budget_min INTEGER,
    budget_max INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(client_id, name)
);

CREATE INDEX IF NOT EXISTS idx_client_project_templates_owner
ON client_project_templates(client_id, updated_at DESC);
