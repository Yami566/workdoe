-- Keep canonical work buckets deterministic while improving human-language recall.
PRAGMA foreign_keys = ON;

ALTER TABLE service_types ADD COLUMN icon_name TEXT;

UPDATE service_types
SET icon_name = CASE slug
    WHEN 'lawn-mowing' THEN 'lawn-mower.svg'
    WHEN 'lawn-care' THEN 'seedling.svg'
    WHEN 'gardening-planting' THEN 'plant.svg'
    WHEN 'weed-removal' THEN 'shovel.svg'
    WHEN 'leaf-cleanup' THEN 'leaf.svg'
    WHEN 'hedge-trimming' THEN 'scissors.svg'
    WHEN 'tree-service' THEN 'tree.svg'
    WHEN 'landscaping' THEN 'garden-cart.svg'
    WHEN 'fencing' THEN 'fence.svg'
    WHEN 'deck-patio' THEN 'building-cottage.svg'
    WHEN 'snow-removal' THEN 'snowflake.svg'
    WHEN 'pressure-washing' THEN 'wash.svg'
    WHEN 'house-cleaning' THEN 'vacuum-cleaner.svg'
    WHEN 'deep-cleaning' THEN 'sparkles.svg'
    WHEN 'move-cleaning' THEN 'home-check.svg'
    WHEN 'window-cleaning' THEN 'window.svg'
    WHEN 'carpet-upholstery' THEN 'sofa.svg'
    WHEN 'gutter-cleaning' THEN 'droplet-down.svg'
    WHEN 'commercial-cleaning' THEN 'building.svg'
    WHEN 'post-construction-cleaning' THEN 'wash.svg'
    WHEN 'local-moving' THEN 'truck.svg'
    WHEN 'packing-unpacking' THEN 'package.svg'
    WHEN 'heavy-lifting' THEN 'weight.svg'
    WHEN 'furniture-appliance-moving' THEN 'fridge.svg'
    WHEN 'office-moving' THEN 'building-skyscraper.svg'
    WHEN 'junk-removal' THEN 'trash.svg'
    WHEN 'donation-pickup' THEN 'gift.svg'
    WHEN 'general-handyman' THEN 'tool.svg'
    WHEN 'furniture-assembly' THEN 'armchair.svg'
    WHEN 'mounting-installation' THEN 'hammer-drill.svg'
    WHEN 'doors-windows' THEN 'door.svg'
    WHEN 'carpentry' THEN 'hammer.svg'
    WHEN 'drywall-repair' THEN 'wall.svg'
    WHEN 'appliance-repair-installation' THEN 'wash-machine.svg'
    WHEN 'locks-home-security' THEN 'lock.svg'
    WHEN 'other-service' THEN 'dots.svg'
    WHEN 'kitchen-remodel' THEN 'tools-kitchen-2.svg'
    WHEN 'bathroom-remodel' THEN 'bath.svg'
    WHEN 'basement-remodel' THEN 'stairs-down.svg'
    WHEN 'interior-painting' THEN 'paint.svg'
    WHEN 'exterior-painting' THEN 'brush.svg'
    WHEN 'flooring-tile' THEN 'border-all.svg'
    WHEN 'cabinets-countertops' THEN 'layout-board-split.svg'
    WHEN 'concrete-masonry' THEN 'wall.svg'
    WHEN 'roofing-siding' THEN 'home-up.svg'
    WHEN 'plumbing' THEN 'droplet.svg'
    WHEN 'electrical' THEN 'plug.svg'
    WHEN 'hvac' THEN 'air-conditioning.svg'
    WHEN 'water-heater' THEN 'flame.svg'
    WHEN 'lighting-ceiling-fans' THEN 'bulb.svg'
    WHEN 'generator-backup-power' THEN 'battery-charging.svg'
    WHEN 'insulation-weatherization' THEN 'thermometer.svg'
    WHEN 'drainage-sump-pump' THEN 'droplet-down.svg'
    ELSE 'tool.svg'
END;

INSERT OR REPLACE INTO service_aliases (alias, service_slug)
VALUES
    ('grass cutting', 'lawn-mowing'),
    ('lawn mowing service', 'lawn-mowing'),
    ('lawn maintenance', 'lawn-care'),
    ('yard service', 'landscaping'),
    ('mulch', 'landscaping'),
    ('mulching', 'landscaping'),
    ('gardener', 'gardening-planting'),
    ('planting', 'gardening-planting'),
    ('weeding', 'weed-removal'),
    ('yard cleanup', 'leaf-cleanup'),
    ('leaf removal', 'leaf-cleanup'),
    ('raking', 'leaf-cleanup'),
    ('bush trimming', 'hedge-trimming'),
    ('shrub trimming', 'hedge-trimming'),
    ('tree trimming', 'tree-service'),
    ('arborist', 'tree-service'),
    ('landscape design', 'landscaping'),
    ('fence repair', 'fencing'),
    ('deck repair', 'deck-patio'),
    ('patio repair', 'deck-patio'),
    ('snow plowing', 'snow-removal'),
    ('maid service', 'house-cleaning'),
    ('home cleaning', 'house-cleaning'),
    ('deep clean', 'deep-cleaning'),
    ('move in cleaning', 'move-cleaning'),
    ('move out cleaning', 'move-cleaning'),
    ('window washing', 'window-cleaning'),
    ('carpet cleaning', 'carpet-upholstery'),
    ('upholstery cleaning', 'carpet-upholstery'),
    ('gutters', 'gutter-cleaning'),
    ('office cleaning', 'commercial-cleaning'),
    ('construction cleanup', 'post-construction-cleaning'),
    ('movers', 'local-moving'),
    ('local movers', 'local-moving'),
    ('unpacking', 'packing-unpacking'),
    ('lifting', 'heavy-lifting'),
    ('furniture moving', 'furniture-appliance-moving'),
    ('appliance moving', 'furniture-appliance-moving'),
    ('office movers', 'office-moving'),
    ('trash hauling', 'junk-removal'),
    ('rubbish removal', 'junk-removal'),
    ('donation pickup', 'donation-pickup'),
    ('home repair', 'general-handyman'),
    ('assembly', 'furniture-assembly'),
    ('ikea assembly', 'furniture-assembly'),
    ('tv mounting', 'mounting-installation'),
    ('mounting', 'mounting-installation'),
    ('door repair', 'doors-windows'),
    ('window repair', 'doors-windows'),
    ('woodwork', 'carpentry'),
    ('drywall', 'drywall-repair'),
    ('appliance installation', 'appliance-repair-installation'),
    ('locksmith', 'locks-home-security'),
    ('kitchen renovation', 'kitchen-remodel'),
    ('bathroom renovation', 'bathroom-remodel'),
    ('basement finishing', 'basement-remodel'),
    ('interior painter', 'interior-painting'),
    ('exterior painter', 'exterior-painting'),
    ('flooring', 'flooring-tile'),
    ('tile', 'flooring-tile'),
    ('cabinets', 'cabinets-countertops'),
    ('countertops', 'cabinets-countertops'),
    ('masonry', 'concrete-masonry'),
    ('concrete', 'concrete-masonry'),
    ('roof repair', 'roofing-siding'),
    ('siding', 'roofing-siding'),
    ('plumber', 'plumbing'),
    ('leak repair', 'plumbing'),
    ('electrician', 'electrical'),
    ('wiring', 'electrical'),
    ('ac repair', 'hvac'),
    ('furnace', 'hvac'),
    ('water heater repair', 'water-heater'),
    ('ceiling fan', 'lighting-ceiling-fans'),
    ('backup power', 'generator-backup-power'),
    ('weatherization', 'insulation-weatherization'),
    ('sump pump', 'drainage-sump-pump'),
    ('drainage', 'drainage-sump-pump');
