-- Keep the public map's visible-photo count on an indexed owner/visibility lookup.
CREATE INDEX IF NOT EXISTS idx_job_photos_public_job
ON job_photos(job_id, is_hidden);

PRAGMA optimize;
