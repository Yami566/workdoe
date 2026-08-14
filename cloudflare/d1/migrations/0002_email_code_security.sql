ALTER TABLE login_codes ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE login_codes ADD COLUMN request_ip_hash TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_login_codes_ip_created
ON login_codes(request_ip_hash, created_at);
