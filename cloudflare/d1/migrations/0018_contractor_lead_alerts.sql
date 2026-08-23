ALTER TABLE contractor_lead_preferences
ADD COLUMN lead_alert_preference TEXT NOT NULL DEFAULT 'workdoe'
CHECK (lead_alert_preference IN ('workdoe', 'email'));

ALTER TABLE contractor_lead_preferences
ADD COLUMN lead_alert_consent_at TEXT;

UPDATE contractor_lead_preferences
SET lead_alert_preference = 'workdoe',
    lead_alert_consent_at = NULL;

CREATE TABLE IF NOT EXISTS contractor_lead_alert_deliveries (
    id INTEGER PRIMARY KEY,
    contractor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'queued', 'sent', 'failed')
    ),
    created_at TEXT NOT NULL,
    queued_at TEXT,
    sent_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(contractor_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_contractor_lead_alert_deliveries_status
ON contractor_lead_alert_deliveries(status, updated_at);
