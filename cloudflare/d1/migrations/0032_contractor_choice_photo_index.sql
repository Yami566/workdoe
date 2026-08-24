CREATE INDEX IF NOT EXISTS idx_contractor_photos_public_contractor
ON contractor_photos(contractor_id, is_hidden, created_at DESC, id DESC);

PRAGMA optimize;
