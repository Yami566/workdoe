-- Deterministic six-family service taxonomy for guided project posting.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS service_groups (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    icon_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS service_types (
    slug TEXT PRIMARY KEY,
    group_slug TEXT NOT NULL REFERENCES service_groups(slug),
    name TEXT NOT NULL,
    legacy_category TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    UNIQUE(group_slug, name)
);

CREATE TABLE IF NOT EXISTS service_aliases (
    alias TEXT PRIMARY KEY COLLATE NOCASE,
    service_slug TEXT NOT NULL REFERENCES service_types(slug) ON DELETE CASCADE
);

INSERT OR IGNORE INTO service_groups
    (slug, name, description, icon_name, sort_order, active)
VALUES
    ('outdoor-yard', 'Outdoor & yard', 'Lawns, gardens, trees and exterior care', 'trees.svg', 1, 1),
    ('cleaning-upkeep', 'Cleaning & upkeep', 'Homes, windows, turnovers and workplaces', 'spray.svg', 2, 1),
    ('moving-hauling', 'Moving & hauling', 'Packing, lifting, delivery and removal', 'truck-delivery.svg', 3, 1),
    ('repairs-installation', 'Repairs & installation', 'Handyman work, assembly and everyday fixes', 'tools.svg', 4, 1),
    ('remodel-finish', 'Remodel & finish', 'Kitchens, baths, paint and finished surfaces', 'paint.svg', 5, 1),
    ('home-systems', 'Home systems', 'Plumbing, electrical, HVAC and utilities', 'bolt.svg', 6, 1);

INSERT OR IGNORE INTO service_types
    (slug, group_slug, name, legacy_category, sort_order, active)
VALUES
    ('lawn-mowing', 'outdoor-yard', 'Lawn mowing', 'Landscaping', 1, 1),
    ('lawn-care', 'outdoor-yard', 'Lawn care', 'Landscaping', 2, 1),
    ('gardening-planting', 'outdoor-yard', 'Gardening & planting', 'Landscaping', 3, 1),
    ('weed-removal', 'outdoor-yard', 'Weed removal', 'Landscaping', 4, 1),
    ('leaf-cleanup', 'outdoor-yard', 'Leaf cleanup', 'Landscaping', 5, 1),
    ('hedge-trimming', 'outdoor-yard', 'Hedge trimming', 'Landscaping', 6, 1),
    ('tree-service', 'outdoor-yard', 'Tree service', 'Tree service', 7, 1),
    ('landscaping', 'outdoor-yard', 'Landscape design & installation', 'Landscaping', 8, 1),
    ('fencing', 'outdoor-yard', 'Fence work', 'Fencing', 9, 1),
    ('deck-patio', 'outdoor-yard', 'Deck & patio work', 'Decks and patios', 10, 1),
    ('snow-removal', 'outdoor-yard', 'Snow removal', 'Landscaping', 11, 1),
    ('pressure-washing', 'outdoor-yard', 'Pressure washing', 'Power washing', 12, 1),
    ('house-cleaning', 'cleaning-upkeep', 'House cleaning', 'Commercial maintenance', 1, 1),
    ('deep-cleaning', 'cleaning-upkeep', 'Deep cleaning', 'Commercial maintenance', 2, 1),
    ('move-cleaning', 'cleaning-upkeep', 'Move-in or move-out cleaning', 'Commercial maintenance', 3, 1),
    ('window-cleaning', 'cleaning-upkeep', 'Window cleaning', 'Window cleaning', 4, 1),
    ('carpet-upholstery', 'cleaning-upkeep', 'Carpet & upholstery cleaning', 'Commercial maintenance', 5, 1),
    ('gutter-cleaning', 'cleaning-upkeep', 'Gutter cleaning', 'Commercial maintenance', 6, 1),
    ('commercial-cleaning', 'cleaning-upkeep', 'Commercial cleaning', 'Commercial maintenance', 7, 1),
    ('post-construction-cleaning', 'cleaning-upkeep', 'Post-construction cleaning', 'Commercial maintenance', 8, 1),
    ('local-moving', 'moving-hauling', 'Local moving', 'Junk removal', 1, 1),
    ('packing-unpacking', 'moving-hauling', 'Packing & unpacking', 'Junk removal', 2, 1),
    ('heavy-lifting', 'moving-hauling', 'Heavy lifting', 'Junk removal', 3, 1),
    ('furniture-appliance-moving', 'moving-hauling', 'Furniture & appliance moving', 'Junk removal', 4, 1),
    ('office-moving', 'moving-hauling', 'Office moving', 'Junk removal', 5, 1),
    ('junk-removal', 'moving-hauling', 'Junk removal', 'Junk removal', 6, 1),
    ('donation-pickup', 'moving-hauling', 'Donation pickup', 'Junk removal', 7, 1),
    ('general-handyman', 'repairs-installation', 'General handyman', 'General handyman', 1, 1),
    ('furniture-assembly', 'repairs-installation', 'Furniture assembly', 'General handyman', 2, 1),
    ('mounting-installation', 'repairs-installation', 'Mounting & installation', 'General handyman', 3, 1),
    ('doors-windows', 'repairs-installation', 'Door & window repair', 'General handyman', 4, 1),
    ('carpentry', 'repairs-installation', 'Carpentry', 'General handyman', 5, 1),
    ('drywall-repair', 'repairs-installation', 'Drywall repair', 'Drywall', 6, 1),
    ('appliance-repair-installation', 'repairs-installation', 'Appliance repair & installation', 'General handyman', 7, 1),
    ('locks-home-security', 'repairs-installation', 'Locks & home security', 'General handyman', 8, 1),
    ('other-service', 'repairs-installation', 'Something else', 'Other', 9, 1),
    ('kitchen-remodel', 'remodel-finish', 'Kitchen remodel', 'Other', 1, 1),
    ('bathroom-remodel', 'remodel-finish', 'Bathroom remodel', 'Other', 2, 1),
    ('basement-remodel', 'remodel-finish', 'Basement remodel', 'Other', 3, 1),
    ('interior-painting', 'remodel-finish', 'Interior painting', 'Painting', 4, 1),
    ('exterior-painting', 'remodel-finish', 'Exterior painting', 'Painting', 5, 1),
    ('flooring-tile', 'remodel-finish', 'Flooring & tile', 'Flooring', 6, 1),
    ('cabinets-countertops', 'remodel-finish', 'Cabinets & countertops', 'Other', 7, 1),
    ('concrete-masonry', 'remodel-finish', 'Concrete & masonry', 'Concrete and masonry', 8, 1),
    ('roofing-siding', 'remodel-finish', 'Roofing & siding', 'Roofing', 9, 1),
    ('plumbing', 'home-systems', 'Plumbing', 'Plumbing', 1, 1),
    ('electrical', 'home-systems', 'Electrical', 'Electrical', 2, 1),
    ('hvac', 'home-systems', 'Heating & cooling', 'HVAC', 3, 1),
    ('water-heater', 'home-systems', 'Water heater', 'Plumbing', 4, 1),
    ('lighting-ceiling-fans', 'home-systems', 'Lighting & ceiling fans', 'Electrical', 5, 1),
    ('generator-backup-power', 'home-systems', 'Generator & backup power', 'Electrical', 6, 1),
    ('insulation-weatherization', 'home-systems', 'Insulation & weatherization', 'Other', 7, 1),
    ('drainage-sump-pump', 'home-systems', 'Drainage & sump pump', 'Plumbing', 8, 1);

INSERT OR REPLACE INTO service_aliases (alias, service_slug)
VALUES
    ('mowing', 'lawn-mowing'),
    ('lawn service', 'lawn-care'),
    ('yard work', 'landscaping'),
    ('gardening', 'gardening-planting'),
    ('power wash', 'pressure-washing'),
    ('power washing', 'pressure-washing'),
    ('powerwashing', 'pressure-washing'),
    ('housekeeping', 'house-cleaning'),
    ('cleaning', 'house-cleaning'),
    ('moving', 'local-moving'),
    ('packing', 'packing-unpacking'),
    ('hauling', 'junk-removal'),
    ('handyman', 'general-handyman'),
    ('painting', 'interior-painting'),
    ('heating and cooling', 'hvac'),
    ('air conditioning', 'hvac'),
    ('other', 'other-service');

ALTER TABLE jobs ADD COLUMN service_group_slug TEXT REFERENCES service_groups(slug);
ALTER TABLE jobs ADD COLUMN service_slug TEXT REFERENCES service_types(slug);
ALTER TABLE job_drafts ADD COLUMN service_group_slug TEXT REFERENCES service_groups(slug);
ALTER TABLE job_drafts ADD COLUMN service_slug TEXT REFERENCES service_types(slug);

UPDATE jobs
SET service_slug = CASE category
        WHEN 'Power washing' THEN 'pressure-washing'
        WHEN 'Window cleaning' THEN 'window-cleaning'
        WHEN 'Roofing' THEN 'roofing-siding'
        WHEN 'Painting' THEN 'interior-painting'
        WHEN 'Drywall' THEN 'drywall-repair'
        WHEN 'Flooring' THEN 'flooring-tile'
        WHEN 'Electrical' THEN 'electrical'
        WHEN 'Plumbing' THEN 'plumbing'
        WHEN 'HVAC' THEN 'hvac'
        WHEN 'Landscaping' THEN 'landscaping'
        WHEN 'Tree service' THEN 'tree-service'
        WHEN 'Fencing' THEN 'fencing'
        WHEN 'Decks and patios' THEN 'deck-patio'
        WHEN 'Concrete and masonry' THEN 'concrete-masonry'
        WHEN 'Junk removal' THEN 'junk-removal'
        WHEN 'Commercial maintenance' THEN 'commercial-cleaning'
        WHEN 'General handyman' THEN 'general-handyman'
        WHEN 'Other' THEN 'other-service'
        ELSE NULL
    END
WHERE service_slug IS NULL;

UPDATE jobs
SET service_group_slug = (
    SELECT service_types.group_slug
    FROM service_types
    WHERE service_types.slug = jobs.service_slug
)
WHERE service_group_slug IS NULL;

UPDATE job_drafts
SET service_slug = CASE category
        WHEN 'Power washing' THEN 'pressure-washing'
        WHEN 'Window cleaning' THEN 'window-cleaning'
        WHEN 'Roofing' THEN 'roofing-siding'
        WHEN 'Painting' THEN 'interior-painting'
        WHEN 'Drywall' THEN 'drywall-repair'
        WHEN 'Flooring' THEN 'flooring-tile'
        WHEN 'Electrical' THEN 'electrical'
        WHEN 'Plumbing' THEN 'plumbing'
        WHEN 'HVAC' THEN 'hvac'
        WHEN 'Landscaping' THEN 'landscaping'
        WHEN 'Tree service' THEN 'tree-service'
        WHEN 'Fencing' THEN 'fencing'
        WHEN 'Decks and patios' THEN 'deck-patio'
        WHEN 'Concrete and masonry' THEN 'concrete-masonry'
        WHEN 'Junk removal' THEN 'junk-removal'
        WHEN 'Commercial maintenance' THEN 'commercial-cleaning'
        WHEN 'General handyman' THEN 'general-handyman'
        WHEN 'Other' THEN 'other-service'
        ELSE NULL
    END
WHERE service_slug IS NULL;

UPDATE job_drafts
SET service_group_slug = (
    SELECT service_types.group_slug
    FROM service_types
    WHERE service_types.slug = job_drafts.service_slug
)
WHERE service_group_slug IS NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_service_status
ON jobs(status, service_group_slug, service_slug);
