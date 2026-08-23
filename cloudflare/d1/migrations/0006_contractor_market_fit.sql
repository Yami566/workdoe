-- Normalize contractor capabilities and practical DMV coverage areas.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS service_zones (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK (state IN ('DC', 'MD', 'VA')),
    sort_order INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

INSERT OR IGNORE INTO service_zones (slug, name, state, sort_order, active) VALUES
    ('district-of-columbia', 'District of Columbia', 'DC', 1, 1),
    ('montgomery-county-md', 'Montgomery County, MD', 'MD', 2, 1),
    ('prince-georges-county-md', 'Prince George''s County, MD', 'MD', 3, 1),
    ('anne-arundel-county-md', 'Anne Arundel County, MD', 'MD', 4, 1),
    ('howard-county-md', 'Howard County, MD', 'MD', 5, 1),
    ('arlington-county-va', 'Arlington County, VA', 'VA', 6, 1),
    ('alexandria-va', 'Alexandria, VA', 'VA', 7, 1),
    ('fairfax-county-va', 'Fairfax County, VA', 'VA', 8, 1),
    ('loudoun-county-va', 'Loudoun County, VA', 'VA', 9, 1),
    ('prince-william-county-va', 'Prince William County, VA', 'VA', 10, 1);

CREATE TABLE IF NOT EXISTS contractor_service_capabilities (
    contractor_id INTEGER NOT NULL
        REFERENCES contractor_profiles(user_id) ON DELETE CASCADE,
    service_slug TEXT NOT NULL
        REFERENCES service_types(slug) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (contractor_id, service_slug)
);

CREATE TABLE IF NOT EXISTS contractor_service_zones (
    contractor_id INTEGER NOT NULL
        REFERENCES contractor_profiles(user_id) ON DELETE CASCADE,
    zone_slug TEXT NOT NULL
        REFERENCES service_zones(slug) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (contractor_id, zone_slug)
);

CREATE INDEX IF NOT EXISTS idx_contractor_capabilities_service
    ON contractor_service_capabilities(service_slug, contractor_id);
CREATE INDEX IF NOT EXISTS idx_contractor_zones_zone
    ON contractor_service_zones(zone_slug, contractor_id);

WITH legacy_map(trade_name, service_slug) AS (
    VALUES
        ('power washing', 'pressure-washing'),
        ('window cleaning', 'window-cleaning'),
        ('roofing', 'roofing-siding'),
        ('painting', 'interior-painting'),
        ('drywall', 'drywall-repair'),
        ('flooring', 'flooring-tile'),
        ('electrical', 'electrical'),
        ('plumbing', 'plumbing'),
        ('hvac', 'hvac'),
        ('landscaping', 'landscaping'),
        ('tree service', 'tree-service'),
        ('fencing', 'fencing'),
        ('decks and patios', 'deck-patio'),
        ('concrete and masonry', 'concrete-masonry'),
        ('junk removal', 'junk-removal'),
        ('general handyman', 'general-handyman'),
        ('commercial maintenance', 'commercial-cleaning'),
        ('other', 'other-service')
)
INSERT OR IGNORE INTO contractor_service_capabilities
    (contractor_id, service_slug, created_at)
SELECT contractor_profiles.user_id, legacy_map.service_slug, datetime('now')
FROM contractor_profiles
JOIN legacy_map
  ON instr(
      ',' || lower(replace(contractor_profiles.trades, ', ', ',')) || ',',
      ',' || legacy_map.trade_name || ','
  ) > 0;

WITH area_map(zone_slug, keyword) AS (
    VALUES
        ('district-of-columbia', 'dc'),
        ('district-of-columbia', 'washington'),
        ('montgomery-county-md', 'montgomery'),
        ('prince-georges-county-md', 'prince george'),
        ('anne-arundel-county-md', 'anne arundel'),
        ('anne-arundel-county-md', 'annapolis'),
        ('howard-county-md', 'howard'),
        ('arlington-county-va', 'arlington'),
        ('alexandria-va', 'alexandria'),
        ('fairfax-county-va', 'fairfax'),
        ('loudoun-county-va', 'loudoun'),
        ('prince-william-county-va', 'prince william'),
        ('arlington-county-va', 'northern virginia'),
        ('alexandria-va', 'northern virginia'),
        ('fairfax-county-va', 'northern virginia'),
        ('loudoun-county-va', 'northern virginia'),
        ('prince-william-county-va', 'northern virginia')
)
INSERT OR IGNORE INTO contractor_service_zones
    (contractor_id, zone_slug, created_at)
SELECT contractor_profiles.user_id, area_map.zone_slug, datetime('now')
FROM contractor_profiles
JOIN area_map
  ON lower(contractor_profiles.service_area) LIKE '%' || area_map.keyword || '%'
UNION
SELECT contractor_profiles.user_id, service_zones.slug, datetime('now')
FROM contractor_profiles
CROSS JOIN service_zones
WHERE lower(contractor_profiles.service_area) LIKE '%dmv%';
