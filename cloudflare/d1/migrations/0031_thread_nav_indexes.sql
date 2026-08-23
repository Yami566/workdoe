CREATE INDEX IF NOT EXISTS idx_threads_client
ON threads(client_id, id);

CREATE INDEX IF NOT EXISTS idx_threads_contractor
ON threads(contractor_id, id);

PRAGMA optimize;
