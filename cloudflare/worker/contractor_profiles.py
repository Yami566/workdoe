from __future__ import annotations

from urllib.parse import urlparse


PROFILE_BUSINESS_MAX_LENGTH = 120
PROFILE_TRADES_MAX_LENGTH = 240
PROFILE_SERVICE_AREA_MAX_LENGTH = 160
PROFILE_INTRO_MIN_LENGTH = 20
PROFILE_INTRO_MAX_LENGTH = 900
PROFILE_INSURANCE_MAX_LENGTH = 120
PROFILE_LICENSE_MAX_LENGTH = 80
PROFILE_YEARS_MAX = 100
PROFILE_WEBSITE_MAX_LENGTH = 200
PROFILE_PHONE_MAX_LENGTH = 40
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


def cleaned_contractor_profile_payload(payload: dict) -> dict[str, str]:
    trades = selected_trades(payload)
    return {
        "business_name": compact_spaces(payload.get("business_name")),
        "trades": ", ".join(trades),
        "service_area": compact_spaces(payload.get("service_area")),
        "intro": (payload.get("intro") or "").strip(),
        "insurance_status": compact_spaces(payload.get("insurance_status")),
        "license_number": compact_spaces(payload.get("license_number")),
        "years_in_business": compact_spaces(payload.get("years_in_business")),
        "website": compact_spaces(payload.get("website")),
        "phone": compact_spaces(payload.get("phone")),
    }


def validate_contractor_profile_payload(form: dict[str, str]) -> list[str]:
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
        else:
            parsed = urlparse(form["website"])
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append("Use a full website URL that starts with http:// or https://.")
    if len(form["phone"]) > PROFILE_PHONE_MAX_LENGTH:
        errors.append(f"Keep the phone under {PROFILE_PHONE_MAX_LENGTH} characters.")
    return errors


def profile_field_for_error(message: str) -> str:
    if "business name" in message:
        return "business_name"
    if "trade" in message:
        return "trades"
    if "service area" in message:
        return "service_area"
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
    if "phone" in message:
        return "phone"
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
    return {**form, "years_in_business_value": profile_years_value(form["years_in_business"])}


def profile_years_value(value: str):
    return int(value) if value else None


def can_update_contractor_profile(user) -> bool:
    return bool(user) and row_value(user, "status") == "active" and row_value(user, "role") == "contractor"


def contractor_profile_response(profile) -> dict:
    return {
        "business_name": row_value(profile, "business_name", "") or "",
        "trades": row_value(profile, "trades", "") or "",
        "service_area": row_value(profile, "service_area", "") or "",
        "intro": row_value(profile, "intro", "") or "",
        "insurance_status": row_value(profile, "insurance_status", "") or "",
        "license_number": row_value(profile, "license_number", "") or "",
        "years_in_business": row_value(profile, "years_in_business"),
        "website": row_value(profile, "website", "") or "",
        "phone": row_value(profile, "phone", "") or "",
        "updated_at": row_value(profile, "updated_at", "") or "",
    }
