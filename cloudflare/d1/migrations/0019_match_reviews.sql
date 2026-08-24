CREATE TABLE IF NOT EXISTS match_reviews (
    id INTEGER PRIMARY KEY,
    match_request_id INTEGER NOT NULL REFERENCES match_requests(id) ON DELETE CASCADE,
    reviewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reviewer_role TEXT NOT NULL CHECK (reviewer_role IN ('client', 'contractor')),
    communication TEXT NOT NULL CHECK (
        communication IN ('met', 'mixed', 'concern', 'not_applicable')
    ),
    scope_accuracy TEXT NOT NULL CHECK (
        scope_accuracy IN ('met', 'mixed', 'concern', 'not_applicable')
    ),
    timeliness TEXT NOT NULL CHECK (
        timeliness IN ('met', 'mixed', 'concern', 'not_applicable')
    ),
    work_outcome TEXT NOT NULL CHECK (
        work_outcome IN ('met', 'mixed', 'concern', 'not_applicable')
    ),
    would_work_again TEXT NOT NULL CHECK (
        would_work_again IN ('yes', 'unsure', 'no')
    ),
    comment TEXT NOT NULL DEFAULT '',
    response TEXT NOT NULL DEFAULT '',
    response_at TEXT,
    is_hidden INTEGER NOT NULL DEFAULT 0 CHECK (is_hidden IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(match_request_id, reviewer_id)
);

CREATE TABLE IF NOT EXISTS match_review_reports (
    id INTEGER PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES match_reviews(id) ON DELETE CASCADE,
    reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    UNIQUE(review_id, reporter_id)
);

CREATE INDEX IF NOT EXISTS idx_match_reviews_subject
ON match_reviews(subject_id, reviewer_role, is_hidden, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_match_review_reports_status
ON match_review_reports(status, created_at DESC);
