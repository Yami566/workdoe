CREATE UNIQUE INDEX IF NOT EXISTS idx_match_requests_one_approved_per_job
ON match_requests(job_id)
WHERE status = 'approved';

PRAGMA optimize;
