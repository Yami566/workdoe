from __future__ import annotations

from .service_taxonomy import SERVICE_BY_SLUG

SERVICE_POLICY_VERSION = "2026-08-22"

STANDARD_SERVICES = frozenset(
    {
        "lawn-mowing",
        "lawn-care",
        "gardening-planting",
        "weed-removal",
        "leaf-cleanup",
        "hedge-trimming",
        "house-cleaning",
        "deep-cleaning",
        "move-cleaning",
        "carpet-upholstery",
        "commercial-cleaning",
        "packing-unpacking",
        "donation-pickup",
        "furniture-assembly",
        "drywall-repair",
        "interior-painting",
    }
)

REGULATED_SERVICES = frozenset(
    {
        "deck-patio",
        "kitchen-remodel",
        "bathroom-remodel",
        "basement-remodel",
        "concrete-masonry",
        "roofing-siding",
        "plumbing",
        "electrical",
        "hvac",
        "water-heater",
        "lighting-ceiling-fans",
        "generator-backup-power",
        "drainage-sump-pump",
    }
)

EMERGENCY_DISABLED_SERVICES = frozenset()

TIER_ADVISORIES = {
    "standard": (
        "Confirm the scope, access, price, materials, and timing directly before work begins."
    ),
    "elevated": (
        "This work may involve heights, heavy loads, power tools, security access, or "
        "property damage. Confirm experience, insurance, site conditions, and a safe work "
        "plan before approval. Workdoe does not verify provider credentials."
    ),
    "regulated": (
        "Permit, license, inspection, and utility requirements vary by jurisdiction. Confirm "
        "them directly with the provider and the appropriate local authority before work "
        "begins. Workdoe does not verify provider credentials."
    ),
}


def _risk_tier(service_slug: str) -> str:
    if service_slug in REGULATED_SERVICES:
        return "regulated"
    if service_slug in STANDARD_SERVICES:
        return "standard"
    return "elevated"


SERVICE_POLICY_REGISTRY = {
    service_slug: {
        "service_slug": service_slug,
        "family": service["group_slug"],
        "risk_tier": _risk_tier(service_slug),
        "advisory": TIER_ADVISORIES[_risk_tier(service_slug)],
        "acknowledgement_required": _risk_tier(service_slug)
        in {"elevated", "regulated"},
        "emergency_disabled": service_slug in EMERGENCY_DISABLED_SERVICES,
        "version": SERVICE_POLICY_VERSION,
    }
    for service_slug, service in SERVICE_BY_SLUG.items()
}

if set(SERVICE_POLICY_REGISTRY) != set(SERVICE_BY_SLUG):
    raise RuntimeError("Every Workdoe service must have a current safety policy.")


def service_policy(service_slug: str | None) -> dict:
    return SERVICE_POLICY_REGISTRY.get(
        str(service_slug or "").strip(),
        {
            "service_slug": "",
            "family": "",
            "risk_tier": "standard",
            "advisory": TIER_ADVISORIES["standard"],
            "acknowledgement_required": False,
            "emergency_disabled": False,
            "version": SERVICE_POLICY_VERSION,
        },
    )


def service_policy_error(
    service_slug: str | None,
    acknowledgement_version: str | None,
) -> str:
    policy = service_policy(service_slug)
    if policy["emergency_disabled"]:
        return "This service is temporarily unavailable for safety review."
    if (
        policy["acknowledgement_required"]
        and str(acknowledgement_version or "").strip() != policy["version"]
    ):
        return "Confirm the current service safety advisory."
    return ""
