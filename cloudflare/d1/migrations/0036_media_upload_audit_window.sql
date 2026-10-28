-- Keep rolling media-upload checks bounded as event history grows. The user id
-- remains inside the redacted event payload; no new personal-data column is
-- introduced for this operational limit.
CREATE INDEX IF NOT EXISTS idx_automation_events_media_upload_window
ON automation_events(event_type, created_at)
WHERE event_type = 'media-uploaded';
