CREATE TABLE IF NOT EXISTS contractor_lead_preferences (
    contractor_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    availability_status TEXT NOT NULL DEFAULT 'available' CHECK (
        availability_status IN ('available', 'limited', 'unavailable')
    ),
    available_from TEXT,
    saved_query TEXT NOT NULL DEFAULT '',
    saved_category TEXT NOT NULL DEFAULT '',
    saved_sort TEXT NOT NULL DEFAULT 'newest' CHECK (
        saved_sort IN ('newest', 'soonest', 'city')
    ),
    saved_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contractor_lead_preferences_availability
ON contractor_lead_preferences(availability_status, available_from);
