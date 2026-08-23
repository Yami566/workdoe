from __future__ import annotations


SERVICE_GROUPS = (
    {
        "slug": "outdoor-yard",
        "name": "Yard & landscaping",
        "description": "Mowing, gardening, trees and exterior care",
        "icon": "trees.svg",
        "quick_count": 6,
        "services": (
            ("lawn-mowing", "Lawn mowing", "Landscaping"),
            ("lawn-care", "Lawn care", "Landscaping"),
            ("gardening-planting", "Gardening & planting", "Landscaping"),
            ("weed-removal", "Weed removal", "Landscaping"),
            ("leaf-cleanup", "Leaf cleanup", "Landscaping"),
            ("hedge-trimming", "Hedge trimming", "Landscaping"),
            ("tree-service", "Tree service", "Tree service"),
            ("landscaping", "Landscape design & installation", "Landscaping"),
            ("fencing", "Fence work", "Fencing"),
            ("deck-patio", "Deck & patio work", "Decks and patios"),
            ("snow-removal", "Snow removal", "Landscaping"),
            ("pressure-washing", "Pressure washing", "Power washing"),
        ),
    },
    {
        "slug": "cleaning-upkeep",
        "name": "Cleaning",
        "description": "Homes, windows, turnovers and workplaces",
        "icon": "spray.svg",
        "quick_count": 6,
        "services": (
            ("house-cleaning", "House cleaning", "Commercial maintenance"),
            ("deep-cleaning", "Deep cleaning", "Commercial maintenance"),
            ("move-cleaning", "Move-in or move-out cleaning", "Commercial maintenance"),
            ("window-cleaning", "Window cleaning", "Window cleaning"),
            ("carpet-upholstery", "Carpet & upholstery cleaning", "Commercial maintenance"),
            ("gutter-cleaning", "Gutter cleaning", "Commercial maintenance"),
            ("commercial-cleaning", "Commercial cleaning", "Commercial maintenance"),
            ("post-construction-cleaning", "Post-construction cleaning", "Commercial maintenance"),
        ),
    },
    {
        "slug": "moving-hauling",
        "name": "Moving & hauling",
        "description": "Packing, lifting, delivery and removal",
        "icon": "truck-delivery.svg",
        "quick_count": 6,
        "services": (
            ("local-moving", "Local moving", "Junk removal"),
            ("packing-unpacking", "Packing & unpacking", "Junk removal"),
            ("heavy-lifting", "Heavy lifting", "Junk removal"),
            ("furniture-appliance-moving", "Furniture & appliance moving", "Junk removal"),
            ("office-moving", "Office moving", "Junk removal"),
            ("junk-removal", "Junk removal", "Junk removal"),
            ("donation-pickup", "Donation pickup", "Junk removal"),
        ),
    },
    {
        "slug": "repairs-installation",
        "name": "Handyman & repairs",
        "description": "Assembly, installation and everyday fixes",
        "icon": "tools.svg",
        "quick_count": 6,
        "services": (
            ("general-handyman", "General handyman", "General handyman"),
            ("furniture-assembly", "Furniture assembly", "General handyman"),
            ("mounting-installation", "Mounting & installation", "General handyman"),
            ("doors-windows", "Door & window repair", "General handyman"),
            ("carpentry", "Carpentry", "General handyman"),
            ("drywall-repair", "Drywall repair", "Drywall"),
            ("appliance-repair-installation", "Appliance repair & installation", "General handyman"),
            ("locks-home-security", "Locks & home security", "General handyman"),
            ("other-service", "Something else", "Other"),
        ),
    },
    {
        "slug": "remodel-finish",
        "name": "Remodeling",
        "description": "Kitchens, baths, paint and finished surfaces",
        "icon": "paint.svg",
        "quick_count": 6,
        "services": (
            ("kitchen-remodel", "Kitchen remodel", "Other"),
            ("bathroom-remodel", "Bathroom remodel", "Other"),
            ("basement-remodel", "Basement remodel", "Other"),
            ("interior-painting", "Interior painting", "Painting"),
            ("exterior-painting", "Exterior painting", "Painting"),
            ("flooring-tile", "Flooring & tile", "Flooring"),
            ("cabinets-countertops", "Cabinets & countertops", "Other"),
            ("concrete-masonry", "Concrete & masonry", "Concrete and masonry"),
            ("roofing-siding", "Roofing & siding", "Roofing"),
        ),
    },
    {
        "slug": "home-systems",
        "name": "Plumbing & systems",
        "description": "Plumbing, electrical, HVAC and utilities",
        "icon": "bolt.svg",
        "quick_count": 6,
        "services": (
            ("plumbing", "Plumbing", "Plumbing"),
            ("electrical", "Electrical", "Electrical"),
            ("hvac", "Heating & cooling", "HVAC"),
            ("water-heater", "Water heater", "Plumbing"),
            ("lighting-ceiling-fans", "Lighting & ceiling fans", "Electrical"),
            ("generator-backup-power", "Generator & backup power", "Electrical"),
            ("insulation-weatherization", "Insulation & weatherization", "Other"),
            ("drainage-sump-pump", "Drainage & sump pump", "Plumbing"),
        ),
    },
)


SERVICE_ICON_BY_SLUG = {
    "lawn-mowing": "lawn-mower.svg",
    "lawn-care": "seedling.svg",
    "gardening-planting": "plant.svg",
    "weed-removal": "shovel.svg",
    "leaf-cleanup": "leaf.svg",
    "hedge-trimming": "scissors.svg",
    "tree-service": "tree.svg",
    "landscaping": "garden-cart.svg",
    "fencing": "fence.svg",
    "deck-patio": "building-cottage.svg",
    "snow-removal": "snowflake.svg",
    "pressure-washing": "wash.svg",
    "house-cleaning": "vacuum-cleaner.svg",
    "deep-cleaning": "sparkles.svg",
    "move-cleaning": "home-check.svg",
    "window-cleaning": "window.svg",
    "carpet-upholstery": "sofa.svg",
    "gutter-cleaning": "droplet-down.svg",
    "commercial-cleaning": "building.svg",
    "post-construction-cleaning": "wash.svg",
    "local-moving": "truck.svg",
    "packing-unpacking": "package.svg",
    "heavy-lifting": "weight.svg",
    "furniture-appliance-moving": "fridge.svg",
    "office-moving": "building-skyscraper.svg",
    "junk-removal": "trash.svg",
    "donation-pickup": "gift.svg",
    "general-handyman": "tool.svg",
    "furniture-assembly": "armchair.svg",
    "mounting-installation": "hammer-drill.svg",
    "doors-windows": "door.svg",
    "carpentry": "hammer.svg",
    "drywall-repair": "wall.svg",
    "appliance-repair-installation": "wash-machine.svg",
    "locks-home-security": "lock.svg",
    "other-service": "dots.svg",
    "kitchen-remodel": "tools-kitchen-2.svg",
    "bathroom-remodel": "bath.svg",
    "basement-remodel": "stairs-down.svg",
    "interior-painting": "paint.svg",
    "exterior-painting": "brush.svg",
    "flooring-tile": "border-all.svg",
    "cabinets-countertops": "layout-board-split.svg",
    "concrete-masonry": "wall.svg",
    "roofing-siding": "home-up.svg",
    "plumbing": "droplet.svg",
    "electrical": "plug.svg",
    "hvac": "air-conditioning.svg",
    "water-heater": "flame.svg",
    "lighting-ceiling-fans": "bulb.svg",
    "generator-backup-power": "battery-charging.svg",
    "insulation-weatherization": "thermometer.svg",
    "drainage-sump-pump": "droplet-down.svg",
}


SERVICE_BY_SLUG = {
    service[0]: {
        "slug": service[0],
        "name": service[1],
        "category": service[2],
        "group_slug": group["slug"],
        "group_name": group["name"],
        "icon": SERVICE_ICON_BY_SLUG.get(service[0], group["icon"]),
    }
    for group in SERVICE_GROUPS
    for service in group["services"]
}
GROUP_BY_SLUG = {group["slug"]: group for group in SERVICE_GROUPS}

SERVICE_ALIASES = {
    "mowing": "lawn-mowing",
    "grass cutting": "lawn-mowing",
    "lawn mowing service": "lawn-mowing",
    "lawn service": "lawn-care",
    "lawn maintenance": "lawn-care",
    "yard work": "landscaping",
    "yard service": "landscaping",
    "mulch": "landscaping",
    "mulching": "landscaping",
    "gardening": "gardening-planting",
    "gardener": "gardening-planting",
    "planting": "gardening-planting",
    "weeding": "weed-removal",
    "yard cleanup": "leaf-cleanup",
    "leaf removal": "leaf-cleanup",
    "raking": "leaf-cleanup",
    "bush trimming": "hedge-trimming",
    "shrub trimming": "hedge-trimming",
    "tree trimming": "tree-service",
    "arborist": "tree-service",
    "landscape design": "landscaping",
    "fence repair": "fencing",
    "deck repair": "deck-patio",
    "patio repair": "deck-patio",
    "snow plowing": "snow-removal",
    "power wash": "pressure-washing",
    "power washing": "pressure-washing",
    "powerwashing": "pressure-washing",
    "housekeeping": "house-cleaning",
    "maid service": "house-cleaning",
    "home cleaning": "house-cleaning",
    "cleaning": "house-cleaning",
    "deep clean": "deep-cleaning",
    "move in cleaning": "move-cleaning",
    "move out cleaning": "move-cleaning",
    "window washing": "window-cleaning",
    "carpet cleaning": "carpet-upholstery",
    "upholstery cleaning": "carpet-upholstery",
    "gutters": "gutter-cleaning",
    "office cleaning": "commercial-cleaning",
    "construction cleanup": "post-construction-cleaning",
    "moving": "local-moving",
    "movers": "local-moving",
    "local movers": "local-moving",
    "packing": "packing-unpacking",
    "unpacking": "packing-unpacking",
    "lifting": "heavy-lifting",
    "furniture moving": "furniture-appliance-moving",
    "appliance moving": "furniture-appliance-moving",
    "office movers": "office-moving",
    "hauling": "junk-removal",
    "trash hauling": "junk-removal",
    "rubbish removal": "junk-removal",
    "donation pickup": "donation-pickup",
    "handyman": "general-handyman",
    "home repair": "general-handyman",
    "assembly": "furniture-assembly",
    "ikea assembly": "furniture-assembly",
    "tv mounting": "mounting-installation",
    "mounting": "mounting-installation",
    "door repair": "doors-windows",
    "window repair": "doors-windows",
    "woodwork": "carpentry",
    "drywall": "drywall-repair",
    "appliance installation": "appliance-repair-installation",
    "locksmith": "locks-home-security",
    "painting": "interior-painting",
    "kitchen renovation": "kitchen-remodel",
    "bathroom renovation": "bathroom-remodel",
    "basement finishing": "basement-remodel",
    "interior painter": "interior-painting",
    "exterior painter": "exterior-painting",
    "flooring": "flooring-tile",
    "tile": "flooring-tile",
    "cabinets": "cabinets-countertops",
    "countertops": "cabinets-countertops",
    "masonry": "concrete-masonry",
    "concrete": "concrete-masonry",
    "roof repair": "roofing-siding",
    "siding": "roofing-siding",
    "plumber": "plumbing",
    "leak repair": "plumbing",
    "electrician": "electrical",
    "wiring": "electrical",
    "heating and cooling": "hvac",
    "air conditioning": "hvac",
    "ac repair": "hvac",
    "furnace": "hvac",
    "water heater repair": "water-heater",
    "ceiling fan": "lighting-ceiling-fans",
    "backup power": "generator-backup-power",
    "weatherization": "insulation-weatherization",
    "sump pump": "drainage-sump-pump",
    "drainage": "drainage-sump-pump",
    "other": "other-service",
}

LEGACY_CATEGORY_DEFAULTS = {
    "Power washing": "pressure-washing",
    "Window cleaning": "window-cleaning",
    "Roofing": "roofing-siding",
    "Painting": "interior-painting",
    "Drywall": "drywall-repair",
    "Flooring": "flooring-tile",
    "Electrical": "electrical",
    "Plumbing": "plumbing",
    "HVAC": "hvac",
    "Landscaping": "landscaping",
    "Tree service": "tree-service",
    "Fencing": "fencing",
    "Decks and patios": "deck-patio",
    "Concrete and masonry": "concrete-masonry",
    "Junk removal": "junk-removal",
    "General handyman": "general-handyman",
    "Commercial maintenance": "commercial-cleaning",
    "Other": "other-service",
}

SERVICE_SLUG_BY_LABEL = {
    " ".join(str(label).strip().lower().split()): slug
    for slug, service in SERVICE_BY_SLUG.items()
    for label in (service["name"], service["category"])
}
SERVICE_SLUG_BY_LABEL.update(
    {
        " ".join(label.strip().lower().split()): slug
        for label, slug in LEGACY_CATEGORY_DEFAULTS.items()
    }
)


def service_slug_from_value(value: str | None) -> str:
    cleaned = " ".join((value or "").strip().lower().split())
    if cleaned in SERVICE_BY_SLUG:
        return cleaned
    return SERVICE_ALIASES.get(cleaned) or SERVICE_SLUG_BY_LABEL.get(cleaned, "")


def service_selection(
    service_slug: str | None,
    group_slug: str | None = None,
    legacy_category: str | None = None,
) -> dict[str, str]:
    explicit_service = bool((service_slug or "").strip())
    normalized_slug = service_slug_from_value(service_slug)
    if not explicit_service and not normalized_slug:
        normalized_slug = LEGACY_CATEGORY_DEFAULTS.get((legacy_category or "").strip(), "")
    service = SERVICE_BY_SLUG.get(normalized_slug)
    if not service:
        return {
            "service_slug": (service_slug or "").strip(),
            "service_group_slug": (group_slug or "").strip(),
            "category": (legacy_category or "").strip(),
        }
    supplied_group = (group_slug or "").strip()
    return {
        "service_slug": service["slug"],
        "service_group_slug": supplied_group or service["group_slug"],
        "category": service["category"],
    }


def service_label(service_slug: str | None, fallback: str = "") -> str:
    service = SERVICE_BY_SLUG.get(service_slug_from_value(service_slug))
    return service["name"] if service else fallback


def service_icon(service_slug: str | None, fallback: str = "tool.svg") -> str:
    service = SERVICE_BY_SLUG.get(service_slug_from_value(service_slug))
    return service["icon"] if service else fallback
