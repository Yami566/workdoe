-- Forward-only support for status-filtered DMV viewport searches.
CREATE INDEX IF NOT EXISTS idx_jobs_open_geo
ON jobs(status, approx_lat, approx_lng, created_at DESC, id DESC);
