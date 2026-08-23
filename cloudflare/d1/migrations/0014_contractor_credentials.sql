CREATE TABLE IF NOT EXISTS contractor_credentials (
    id INTEGER PRIMARY KEY,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_type TEXT NOT NULL CHECK (
        credential_type IN ('trade_license', 'business_registration', 'insurance')
    ),
    jurisdiction TEXT NOT NULL CHECK (
        jurisdiction IN ('DC', 'MD', 'VA', 'FEDERAL', 'OTHER')
    ),
    claimed_identifier TEXT NOT NULL,
    claimed_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'self_reported' CHECK (
        status IN ('self_reported', 'pending', 'verified', 'expired', 'rejected')
    ),
    source_url TEXT NOT NULL DEFAULT '',
    checked_at TEXT,
    expires_at TEXT,
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    review_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(contractor_id, credential_type, jurisdiction, claimed_identifier)
);

CREATE INDEX IF NOT EXISTS idx_contractor_credentials_owner
ON contractor_credentials(contractor_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_contractor_credentials_review
ON contractor_credentials(status, updated_at DESC);
