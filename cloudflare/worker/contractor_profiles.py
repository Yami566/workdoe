from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse, urlunparse

from market_fit import (
    infer_service_slugs_from_trades,
    infer_zone_slugs_from_area,
    legacy_trades_for_services,
    normalize_service_slugs,
    normalize_zone_slugs,
    service_area_label,
)

PROFILE_BUSINESS_MAX_LENGTH = 120
PROFILE_TRADES_MAX_LENGTH = 240
PROFILE_SERVICE_AREA_MAX_LENGTH = 160
PROFILE_INTRO_MIN_LENGTH = 20
PROFILE_INTRO_MAX_LENGTH = 900
PROFILE_INSURANCE_MAX_LENGTH = 120
PROFILE_LICENSE_MAX_LENGTH = 80
PROFILE_YEARS_MAX = 100
PROFILE_WEBSITE_MAX_LENGTH = 200
PROFILE_WEBSITE_ERROR = "Use a public HTTPS website such as https://example.com."
PROFILE_HOST_LABEL_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
MAX_CONTRACTOR_PROFILE_BODY_BYTES = 8192

JOB_CATEGORIES = (
    "Power washing",
    "Window cleaning",
    "Roofing",
    "Painting",
    "Drywall",
    "Flooring",
    "Electrical",
    "Plumbing",
    "HVAC",
    "Landscaping",
    "Tree service",
    "Fencing",
    "Decks and patios",
    "Concrete and masonry",
    "Junk removal",
    "General handyman",
    "Commercial maintenance",
    "Other",
)


class ContractorProfileError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        self.field_errors = profile_field_errors(errors)
        super().__init__("; ".join(errors))


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def selected_trades(payload: dict) -> list[str]:
    raw = payload.get("trades", [])
    if isinstance(raw, str):
        requested = {compact_spaces(item) for item in raw.split(",")}
    elif isinstance(raw, list):
        requested = {compact_spaces(str(item)) for item in raw}
    else:
        requested = set()
    return [category for category in JOB_CATEGORIES if category in requested]


def cleaned_contractor_profile_payload(payload: dict) -> dict:
    structured_market_fit = (
        "service_slugs" in payload
        or "service_zone_slugs" in payload
        or str(payload.get("market_fit_version") or "") == "1"
    )
    if structured_market_fit:
        service_slugs = normalize_service_slugs(payload.get("service_slugs"))
        service_zone_slugs = normalize_zone_slugs(payload.get("service_zone_slugs"))
        trades = legacy_trades_for_services(service_slugs)
        service_area = service_area_label(service_zone_slugs)
    else:
        trades = ", ".join(selected_trades(payload))
        service_area = compact_spaces(payload.get("service_area"))
        service_slugs = infer_service_slugs_from_trades(trades)
        service_zone_slugs = infer_zone_slugs_from_area(service_area)
    return {
        "business_name": compact_spaces(payload.get("business_name")),
        "trades": trades,
        "service_area": service_area,
        "service_slugs": service_slugs,
        "service_zone_slugs": service_zone_slugs,
        "intro": (payload.get("intro") or "").strip(),
        "insurance_status": compact_spaces(payload.get("insurance_status")),
        "license_number": compact_spaces(payload.get("license_number")),
        "years_in_business": compact_spaces(payload.get("years_in_business")),
        "website": compact_spaces(payload.get("website")),
    }


def validate_contractor_profile_payload(form: dict) -> list[str]:
    errors: list[str] = []
    if not form["business_name"]:
        errors.append("Add a business name.")
    elif len(form["business_name"]) > PROFILE_BUSINESS_MAX_LENGTH:
        errors.append(f"Keep the business name under {PROFILE_BUSINESS_MAX_LENGTH} characters.")
    if not form["trades"]:
        errors.append("Choose at least one trade.")
    elif len(form["trades"]) > PROFILE_TRADES_MAX_LENGTH:
        errors.append("Choose fewer trades for the beta profile.")
    if not form["service_area"]:
        errors.append("Add a service area.")
    elif len(form["service_area"]) > PROFILE_SERVICE_AREA_MAX_LENGTH:
        errors.append(f"Keep the service area under {PROFILE_SERVICE_AREA_MAX_LENGTH} characters.")
    if len(form["intro"]) < PROFILE_INTRO_MIN_LENGTH:
        errors.append(f"Add at least {PROFILE_INTRO_MIN_LENGTH} characters about your business.")
    elif len(form["intro"]) > PROFILE_INTRO_MAX_LENGTH:
        errors.append(f"Keep the intro under {PROFILE_INTRO_MAX_LENGTH} characters.")
    if len(form["insurance_status"]) > PROFILE_INSURANCE_MAX_LENGTH:
        errors.append(f"Keep the insurance status under {PROFILE_INSURANCE_MAX_LENGTH} characters.")
    if len(form["license_number"]) > PROFILE_LICENSE_MAX_LENGTH:
        errors.append(f"Keep the license number under {PROFILE_LICENSE_MAX_LENGTH} characters.")
    if form["years_in_business"]:
        try:
            years = int(form["years_in_business"])
        except ValueError:
            errors.append("Use a whole number for years in business.")
        else:
            if years < 0 or years > PROFILE_YEARS_MAX:
                errors.append(f"Use 0 to {PROFILE_YEARS_MAX} for years in business.")
    if form["website"]:
        if len(form["website"]) > PROFILE_WEBSITE_MAX_LENGTH:
            errors.append(f"Keep the website under {PROFILE_WEBSITE_MAX_LENGTH} characters.")
        elif not normalized_profile_website(form["website"]):
            errors.append(PROFILE_WEBSITE_ERROR)
    return errors


def profile_field_for_error(message: str) -> str:
    if "business name" in message:
        return "business_name"
    if "service area" in message:
        return "service_area"
    if "trade" in message or "service" in message:
        return "trades"
    if "years in business" in message:
        return "years_in_business"
    if "business" in message or "intro" in message:
        return "intro"
    if "insurance" in message:
        return "insurance_status"
    if "license" in message:
        return "license_number"
    if "website" in message or "URL" in message:
        return "website"
    return ""


def profile_field_errors(errors: list[str]) -> dict[str, list[str]]:
    field_errors: dict[str, list[str]] = {}
    for message in errors:
        field = profile_field_for_error(message)
        if field:
            field_errors.setdefault(field, []).append(message)
    return field_errors


def contractor_profile_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ContractorProfileError(["Contractor profile payload must be a JSON object."])
    form = cleaned_contractor_profile_payload(payload)
    errors = validate_contractor_profile_payload(form)
    if errors:
        raise ContractorProfileError(errors)
    return {
        **form,
        "website": normalized_profile_website(form["website"]),
        "years_in_business_value": profile_years_value(form["years_in_business"]),
    }


def profile_years_value(value: str):
    return int(value) if value else None


def can_update_contractor_profile(user) -> bool:
    return bool(user) and row_value(user, "status") == "active" and row_value(user, "role") == "contractor"


def normalized_profile_website(value: str | None) -> str:
    raw_value = (value or "").strip()
    if not raw_value or any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in raw_value
    ):
        return ""
    try:
        parsed = urlparse(raw_value)
        port = parsed.port
        hostname = (parsed.hostname or "").rstrip(".")
        ascii_hostname = hostname.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        return ""
    if (
        parsed.scheme.lower() != "https"
        or not ascii_hostname
        or parsed.username
        or parsed.password
        or port not in {None, 443}
        or ascii_hostname == "localhost"
        or "." not in ascii_hostname
        or any(
            not PROFILE_HOST_LABEL_RE.fullmatch(label)
            for label in ascii_hostname.split(".")
        )
    ):
        return ""
    try:
        ipaddress.ip_address(ascii_hostname)
    except ValueError:
        pass
    else:
        return ""
    return urlunparse(
        (
            "https",
            ascii_hostname,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def profile_website_label(value: str | None) -> str:
    safe_website = normalized_profile_website(value)
    hostname = urlparse(safe_website).hostname if safe_website else ""
    return (hostname or "").removeprefix("www.")


def contractor_profile_readiness(profile, photos=None) -> dict:
    service_slugs = normalize_service_slugs(row_value(profile, "service_slugs", None))
    service_zone_slugs = normalize_zone_slugs(
        row_value(profile, "service_zone_slugs", None)
    )
    items = [
        {"label": "Business name", "target": "profile-business-name", "complete": bool(row_value(profile, "business_name", ""))},
        {"label": "About your work", "target": "profile-intro", "complete": len(str(row_value(profile, "intro", "") or "").strip()) >= PROFILE_INTRO_MIN_LENGTH},
        {"label": "Services", "target": "profile-trades", "complete": bool(service_slugs or row_value(profile, "trades", ""))},
        {"label": "Service zones", "target": "profile-service-area", "complete": bool(service_zone_slugs or row_value(profile, "service_area", ""))},
        {"label": "Years active", "target": "profile-years-in-business", "complete": row_value(profile, "years_in_business", None) not in {None, ""}},
        {"label": "HTTPS website", "target": "profile-website", "complete": bool(normalized_profile_website(row_value(profile, "website", "")))},
        {"label": "Portfolio photo", "target": "profile-photos", "complete": bool(photos)},
    ]
    complete_count = sum(1 for item in items if item["complete"])
    return {
        "items": items,
        "complete_count": complete_count,
        "total_count": len(items),
        "percent": round((complete_count / len(items)) * 100),
    }


def contractor_profile_response(profile, service_slugs=None, service_zone_slugs=None) -> dict:
    normalized_services = normalize_service_slugs(
        service_slugs
        if service_slugs is not None
        else row_value(profile, "service_slugs", None)
    )
    normalized_zones = normalize_zone_slugs(
        service_zone_slugs
        if service_zone_slugs is not None
        else row_value(profile, "service_zone_slugs", None)
    )
    if not normalized_services:
        normalized_services = infer_service_slugs_from_trades(row_value(profile, "trades", ""))
    if not normalized_zones:
        normalized_zones = infer_zone_slugs_from_area(row_value(profile, "service_area", ""))
    return {
        "business_name": row_value(profile, "business_name", "") or "",
        "trades": row_value(profile, "trades", "") or "",
        "service_area": row_value(profile, "service_area", "") or "",
        "intro": row_value(profile, "intro", "") or "",
        "insurance_status": row_value(profile, "insurance_status", "") or "",
        "license_number": row_value(profile, "license_number", "") or "",
        "years_in_business": row_value(profile, "years_in_business"),
        "website": normalized_profile_website(row_value(profile, "website", "")),
        "updated_at": row_value(profile, "updated_at", "") or "",
        "service_slugs": normalized_services,
        "service_zone_slugs": normalized_zones,
    }
