ALTER TABLE jobs ADD COLUMN service_zone_slug TEXT;

UPDATE jobs
SET service_zone_slug = CASE
    WHEN state = 'DC' THEN 'district-of-columbia'
    WHEN state = 'MD' AND (
        zip_code LIKE '208%' OR zip_code LIKE '209%'
        OR lower(city) IN ('bethesda', 'chevy chase', 'gaithersburg', 'germantown',
                           'rockville', 'silver spring', 'takoma park', 'wheaton')
    ) THEN 'montgomery-county-md'
    WHEN state = 'MD' AND (
        zip_code LIKE '207%'
        OR lower(city) IN ('berwyn heights', 'bowie', 'college park', 'greenbelt',
                           'hyattsville', 'laurel', 'upper marlboro')
    ) THEN 'prince-georges-county-md'
    WHEN state = 'MD' AND (
        zip_code LIKE '214%'
        OR lower(city) IN ('annapolis', 'glen burnie', 'odenton', 'severna park')
    ) THEN 'anne-arundel-county-md'
    WHEN state = 'MD' AND lower(city) IN (
        'columbia', 'elkridge', 'ellicott city'
    ) THEN 'howard-county-md'
    WHEN state = 'VA' AND (
        zip_code LIKE '222%' OR lower(city) = 'arlington'
    ) THEN 'arlington-county-va'
    WHEN state = 'VA' AND (
        zip_code LIKE '223%' OR lower(city) = 'alexandria'
    ) THEN 'alexandria-va'
    WHEN state = 'VA' AND (
        zip_code LIKE '220%'
        OR lower(city) IN ('annandale', 'burke', 'centreville', 'chantilly',
                           'fairfax', 'falls church', 'herndon', 'mclean', 'reston',
                           'springfield', 'vienna')
    ) THEN 'fairfax-county-va'
    WHEN state = 'VA' AND lower(city) IN ('ashburn', 'leesburg', 'sterling')
        THEN 'loudoun-county-va'
    WHEN state = 'VA' AND lower(city) IN ('dumfries', 'manassas', 'woodbridge')
        THEN 'prince-william-county-va'
    ELSE NULL
END
WHERE service_zone_slug IS NULL OR service_zone_slug = '';

CREATE INDEX IF NOT EXISTS idx_jobs_service_zone_status
    ON jobs(status, service_zone_slug, service_slug);

CREATE TABLE IF NOT EXISTS service_zone_activations (
    service_slug TEXT NOT NULL
        REFERENCES service_types(slug) ON DELETE CASCADE,
    zone_slug TEXT NOT NULL
        REFERENCES service_zones(slug) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'active', 'paused', 'retired')),
    allowed_scope TEXT NOT NULL DEFAULT '',
    excluded_scope TEXT NOT NULL DEFAULT '',
    requirements_summary TEXT NOT NULL DEFAULT '',
    minimum_eligible_contractors INTEGER NOT NULL DEFAULT 3
        CHECK (minimum_eligible_contractors BETWEEN 1 AND 100),
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TEXT,
    reviewed_at TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (service_slug, zone_slug)
);

CREATE INDEX IF NOT EXISTS idx_service_zone_activations_status
    ON service_zone_activations(status, zone_slug, service_slug);

WITH pilot_services(service_slug) AS (
    VALUES
        ('house-cleaning'),
        ('deep-cleaning'),
        ('move-cleaning'),
        ('packing-unpacking'),
        ('heavy-lifting'),
        ('furniture-assembly')
),
pilot_zones(zone_slug) AS (
    VALUES
        ('district-of-columbia'),
        ('arlington-county-va'),
        ('alexandria-va')
)
INSERT OR IGNORE INTO service_zone_activations
    (service_slug, zone_slug, status, allowed_scope, excluded_scope,
     requirements_summary, minimum_eligible_contractors, created_at, updated_at)
SELECT
    pilot_services.service_slug,
    pilot_zones.zone_slug,
    'candidate',
    'Interior cleaning, packing or unpacking, in-home lifting, and freestanding furniture assembly within the selected service definition.',
    'No vehicle transport, disposal, wall attachment, exterior access, utility connection, structural work, or alteration of real property.',
    'Operator review of local business requirements, insurance, worker safety, building access, and service-specific exclusions is required before activation.',
    3,
    datetime('now'),
    datetime('now')
FROM pilot_services
CROSS JOIN pilot_zones;
