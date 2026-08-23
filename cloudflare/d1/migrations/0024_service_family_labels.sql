-- Keep canonical slugs stable while presenting plain-language family labels.
UPDATE service_groups
SET name = 'Yard & landscaping',
    description = 'Mowing, gardening, trees and exterior care'
WHERE slug = 'outdoor-yard';

UPDATE service_groups
SET name = 'Cleaning',
    description = 'Homes, windows, turnovers and workplaces'
WHERE slug = 'cleaning-upkeep';

UPDATE service_groups
SET name = 'Handyman & repairs',
    description = 'Assembly, installation and everyday fixes'
WHERE slug = 'repairs-installation';

UPDATE service_groups
SET name = 'Remodeling',
    description = 'Kitchens, baths, paint and finished surfaces'
WHERE slug = 'remodel-finish';

UPDATE service_groups
SET name = 'Plumbing & systems',
    description = 'Plumbing, electrical, HVAC and utilities'
WHERE slug = 'home-systems';
