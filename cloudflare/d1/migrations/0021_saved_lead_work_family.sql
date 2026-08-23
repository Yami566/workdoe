ALTER TABLE contractor_lead_preferences
ADD COLUMN saved_service_group_slug TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_contractor_lead_preferences_family
ON contractor_lead_preferences(saved_service_group_slug, saved_at);
