CREATE TABLE IF NOT EXISTS job_scope_answers (
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    schema_version INTEGER NOT NULL,
    question_key TEXT NOT NULL,
    answer_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (job_id, question_key)
);

CREATE TABLE IF NOT EXISTS job_draft_scope_answers (
    draft_id INTEGER NOT NULL REFERENCES job_drafts(id) ON DELETE CASCADE,
    schema_version INTEGER NOT NULL,
    question_key TEXT NOT NULL,
    answer_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (draft_id, question_key)
);

CREATE INDEX IF NOT EXISTS idx_job_scope_answers_bucket
ON job_scope_answers(question_key, answer_code, schema_version);

CREATE INDEX IF NOT EXISTS idx_job_draft_scope_answers_bucket
ON job_draft_scope_answers(question_key, answer_code, schema_version);
