from __future__ import annotations

import re

from .service_taxonomy import (
    LEGACY_CATEGORY_DEFAULTS,
    SERVICE_BY_SLUG,
    SERVICE_GROUPS,
    service_slug_from_value,
)

DMV_SERVICE_ZONES = (
    {
        "slug": "district-of-columbia",
        "name": "District of Columbia",
        "short_name": "DC",
        "state": "DC",
        "cities": ("washington",),
        "zip_prefixes": ("200", "202", "203", "204", "205"),
    },
    {
        "slug": "montgomery-county-md",
        "name": "Montgomery County, MD",
        "short_name": "Montgomery County",
        "state": "MD",
        "cities": (
            "bethesda",
            "chevy chase",
            "gaithersburg",
            "germantown",
            "rockville",
            "silver spring",
            "takoma park",
            "wheaton",
        ),
        "zip_prefixes": ("208", "209"),
    },
    {
        "slug": "prince-georges-county-md",
        "name": "Prince George's County, MD",
        "short_name": "Prince George's County",
        "state": "MD",
        "cities": (
            "berwyn heights",
            "bowie",
            "college park",
            "greenbelt",
            "hyattsville",
            "laurel",
            "upper marlboro",
        ),
        "zip_prefixes": ("207",),
    },
    {
        "slug": "anne-arundel-county-md",
        "name": "Anne Arundel County, MD",
        "short_name": "Anne Arundel County",
        "state": "MD",
        "cities": ("annapolis", "glen burnie", "odenton", "severna park"),
        "zip_prefixes": ("214",),
    },
    {
        "slug": "howard-county-md",
        "name": "Howard County, MD",
        "short_name": "Howard County",
        "state": "MD",
        "cities": ("columbia", "elkridge", "ellicott city", "laurel"),
        "zip_prefixes": (),
    },
    {
        "slug": "arlington-county-va",
        "name": "Arlington County, VA",
        "short_name": "Arlington",
        "state": "VA",
        "cities": ("arlington",),
        "zip_prefixes": ("222",),
    },
    {
        "slug": "alexandria-va",
        "name": "Alexandria, VA",
        "short_name": "Alexandria",
        "state": "VA",
        "cities": ("alexandria",),
        "zip_prefixes": ("223",),
    },
    {
        "slug": "fairfax-county-va",
        "name": "Fairfax County, VA",
        "short_name": "Fairfax County",
        "state": "VA",
        "cities": (
            "annandale",
            "burke",
            "centreville",
            "chantilly",
            "fairfax",
            "falls church",
            "herndon",
            "mclean",
            "reston",
            "springfield",
            "vienna",
        ),
        "zip_prefixes": ("220",),
    },
    {
        "slug": "loudoun-county-va",
        "name": "Loudoun County, VA",
        "short_name": "Loudoun County",
        "state": "VA",
        "cities": ("ashburn", "leesburg", "sterling"),
        "zip_prefixes": (),
    },
    {
        "slug": "prince-william-county-va",
        "name": "Prince William County, VA",
        "short_name": "Prince William County",
        "state": "VA",
        "cities": ("dumfries", "manassas", "woodbridge"),
        "zip_prefixes": (),
    },
)

ZONE_BY_SLUG = {zone["slug"]: zone for zone in DMV_SERVICE_ZONES}
SERVICE_SLUG_ORDER = tuple(
    service[0] for group in SERVICE_GROUPS for service in group["services"]
)
ZONE_SLUG_ORDER = tuple(zone["slug"] for zone in DMV_SERVICE_ZONES)
MARYLAND_ZONE_SLUGS = tuple(
    zone["slug"] for zone in DMV_SERVICE_ZONES if zone["state"] == "MD"
)
NORTHERN_VIRGINIA_ZONE_SLUGS = tuple(
    zone["slug"] for zone in DMV_SERVICE_ZONES if zone["state"] == "VA"
)


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return getattr(row, key, default)


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def list_values(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [compact_spaces(str(part)) for part in raw if compact_spaces(str(part))]
    return []


def normalize_service_slugs(raw) -> list[str]:
    requested: set[str] = set()
    for value in list_values(raw):
        slug = service_slug_from_value(value)
        if not slug:
            slug = LEGACY_CATEGORY_DEFAULTS.get(value, "")
        if slug in SERVICE_BY_SLUG:
            requested.add(slug)
    return [slug for slug in SERVICE_SLUG_ORDER if slug in requested]


def normalize_zone_slugs(raw) -> list[str]:
    requested = {value for value in list_values(raw) if value in ZONE_BY_SLUG}
    return [slug for slug in ZONE_SLUG_ORDER if slug in requested]


def infer_service_slugs_from_trades(trades: str | None) -> list[str]:
    return normalize_service_slugs(trades)


def infer_zone_slugs_from_area(service_area: str | None) -> list[str]:
    cleaned = compact_spaces(service_area).lower()
    if not cleaned:
        return []
    if cleaned == "dmv" or "dmv area" in cleaned or "dc metro" in cleaned:
        return list(ZONE_SLUG_ORDER)

    requested: set[str] = set()
    if re.search(r"\b(dc|district of columbia|washington)\b", cleaned):
        requested.add("district-of-columbia")
    if "maryland" in cleaned:
        requested.update(MARYLAND_ZONE_SLUGS)
    if "northern virginia" in cleaned or "nova" in cleaned:
        requested.update(NORTHERN_VIRGINIA_ZONE_SLUGS)
    for zone in DMV_SERVICE_ZONES:
        haystacks = (zone["name"].lower(), zone["short_name"].lower(), *zone["cities"])
        if any(name and name in cleaned for name in haystacks):
            requested.add(zone["slug"])
    return [slug for slug in ZONE_SLUG_ORDER if slug in requested]


def legacy_trades_for_services(service_slugs) -> str:
    selected = set(normalize_service_slugs(service_slugs))
    categories: list[str] = []
    for group in SERVICE_GROUPS:
        for slug, _name, category in group["services"]:
            if slug in selected and category not in categories:
                categories.append(category)
    return ", ".join(categories)


def service_area_label(zone_slugs) -> str:
    normalized = normalize_zone_slugs(zone_slugs)
    if normalized == list(ZONE_SLUG_ORDER):
        return "DMV area"
    return ", ".join(ZONE_BY_SLUG[slug]["name"] for slug in normalized)


def job_zone_slug(city: str | None, state: str | None, zip_code: str | None) -> str:
    normalized_city = compact_spaces(city).lower()
    normalized_state = compact_spaces(state).upper()
    digits = "".join(character for character in str(zip_code or "") if character.isdigit())[:5]
    if normalized_state == "DC":
        return "district-of-columbia"
    for zone in DMV_SERVICE_ZONES:
        if zone["state"] != normalized_state:
            continue
        if normalized_city and normalized_city in zone["cities"]:
            return zone["slug"]
    for zone in DMV_SERVICE_ZONES:
        if zone["state"] != normalized_state:
            continue
        if digits and any(digits.startswith(prefix) for prefix in zone["zip_prefixes"]):
            return zone["slug"]
    return ""


def contractor_fit_for_job(job, service_slugs, zone_slugs) -> dict:
    selected_services = set(normalize_service_slugs(service_slugs))
    selected_zones = set(normalize_zone_slugs(zone_slugs))
    service_slug = service_slug_from_value(row_value(job, "service_slug", ""))
    if not service_slug:
        service_slug = LEGACY_CATEGORY_DEFAULTS.get(row_value(job, "category", "") or "", "")
    zone_slug = job_zone_slug(
        row_value(job, "city", ""),
        row_value(job, "state", ""),
        row_value(job, "zip_code", ""),
    )
    service_match = bool(service_slug and service_slug in selected_services)
    zone_match = bool(zone_slug and zone_slug in selected_zones)
    score = (2 if service_match else 0) + (1 if zone_match else 0)
    labels = {3: "Best fit", 2: "Service fit", 1: "In your area", 0: ""}
    return {
        "fit_score": score,
        "fit_label": labels[score],
        "service_match": service_match,
        "zone_match": zone_match,
        "zone_slug": zone_slug,
    }


def annotate_job_fits(jobs: list, service_slugs, zone_slugs) -> list[dict]:
    annotated: list[dict] = []
    for row in jobs:
        if isinstance(row, dict):
            job = dict(row)
        elif hasattr(row, "keys"):
            job = {key: row[key] for key in row.keys()}  # noqa: SIM118 - keys are columns.
        else:
            job = dict(row)
        job.update(contractor_fit_for_job(job, service_slugs, zone_slugs))
        annotated.append(job)
    return annotated
