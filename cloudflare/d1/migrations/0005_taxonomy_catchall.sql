-- Preserve legacy Other records without mislabeling them as handyman work.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO service_types
    (slug, group_slug, name, legacy_category, sort_order, active)
VALUES
    ('other-service', 'repairs-installation', 'Something else', 'Other', 9, 1);

INSERT OR REPLACE INTO service_aliases (alias, service_slug)
VALUES ('other', 'other-service');

UPDATE jobs
SET service_group_slug = 'repairs-installation', service_slug = 'other-service'
WHERE category = 'Other' AND (service_slug IS NULL OR service_slug = 'general-handyman');

UPDATE job_drafts
SET service_group_slug = 'repairs-installation', service_slug = 'other-service'
WHERE category = 'Other' AND (service_slug IS NULL OR service_slug = 'general-handyman');
