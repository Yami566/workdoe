ALTER TABLE jobs
ADD COLUMN license_preference INTEGER NOT NULL DEFAULT 0
CHECK (license_preference IN (0, 1));

ALTER TABLE job_drafts
ADD COLUMN license_preference INTEGER NOT NULL DEFAULT 0
CHECK (license_preference IN (0, 1));

ALTER TABLE client_project_templates
ADD COLUMN license_preference INTEGER NOT NULL DEFAULT 0
CHECK (license_preference IN (0, 1));
