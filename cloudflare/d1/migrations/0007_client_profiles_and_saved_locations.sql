ALTER TABLE client_profiles
ADD COLUMN account_type TEXT NOT NULL DEFAULT 'household';

ALTER TABLE client_profiles
ADD COLUMN notification_preference TEXT NOT NULL DEFAULT 'email';

ALTER TABLE client_profiles
ADD COLUMN profile_note TEXT NOT NULL DEFAULT '';

ALTER TABLE client_profiles
ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS client_saved_locations (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL
        REFERENCES client_profiles(user_id) ON DELETE CASCADE,
    label TEXT NOT NULL COLLATE NOCASE,
    city TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('DC', 'MD', 'VA')),
    zip_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (client_id, label)
);

CREATE INDEX IF NOT EXISTS idx_client_saved_locations_owner
ON client_saved_locations(client_id, updated_at DESC);

UPDATE client_profiles
SET updated_at = COALESCE(
    NULLIF(updated_at, ''),
    (SELECT users.created_at FROM users WHERE users.id = client_profiles.user_id),
    '2026-08-16T00:00:00+00:00'
)
WHERE updated_at = '';
