from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from .service_taxonomy import GROUP_BY_SLUG, SERVICE_BY_SLUG


AVAILABILITY_OPTIONS = (
    ("available", "Available for new work"),
    ("limited", "Limited availability"),
    ("unavailable", "Not taking new work"),
)
AVAILABILITY_STATUSES = {value for value, _label in AVAILABILITY_OPTIONS}
DEFAULT_AVAILABILITY_STATUS = "available"
DEFAULT_LEAD_SORT = "newest"
SAVED_QUERY_MAX_LENGTH = 80
LEAD_ALERT_OPTIONS = (
    ("workdoe", "Workdoe only"),
    ("email", "Email me about new matches"),
)
LEAD_ALERT_VALUES = {value for value, _label in LEAD_ALERT_OPTIONS}
DEFAULT_LEAD_ALERT_PREFERENCE = "workdoe"


class ContractorPreferenceError(ValueError):
    def __init__(self, errors: list[str], field_errors: dict[str, list[str]] | None = None):
        self.errors = errors
        self.field_errors = field_errors or {}
        super().__init__(" ".join(errors))


def row_value(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, default)


def compact_spaces(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def normalized_available_from(value: str | None) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    try:
        parsed = date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ContractorPreferenceError(
            ["Use a valid next-available date."],
            {"available_from": ["Use a valid next-available date."]},
        ) from exc
    if parsed < date.today():
        raise ContractorPreferenceError(
            ["Next available date cannot be in the past."],
            {"available_from": ["Next available date cannot be in the past."]},
        )
    return parsed.isoformat()


def availability_payload(data: dict) -> dict[str, str]:
    status = str(data.get("availability_status") or "").strip()
    if status not in AVAILABILITY_STATUSES:
        raise ContractorPreferenceError(
            ["Choose a valid availability status."],
            {"availability_status": ["Choose a valid availability status."]},
        )
    available_from = normalized_available_from(data.get("available_from"))
    if status == "available":
        available_from = ""
    return {
        "availability_status": status,
        "available_from": available_from,
    }


def saved_lead_view_payload(
    data: dict,
    *,
    categories,
    sorts,
    families=(),
) -> dict[str, str]:
    query = compact_spaces(data.get("saved_query", data.get("q")))
    if len(query) > SAVED_QUERY_MAX_LENGTH:
        raise ContractorPreferenceError(
            [f"Search must be {SAVED_QUERY_MAX_LENGTH} characters or fewer."],
            {"saved_query": [f"Use {SAVED_QUERY_MAX_LENGTH} characters or fewer."]},
        )
    category = str(data.get("saved_category", data.get("category")) or "").strip()
    if category and category not in set(categories):
        raise ContractorPreferenceError(
            ["Choose a valid project category."],
            {"saved_category": ["Choose a valid project category."]},
        )
    family = str(
        data.get("saved_service_group_slug", data.get("family")) or ""
    ).strip()
    if family and family not in set(families):
        raise ContractorPreferenceError(
            ["Choose a valid work family."],
            {"saved_service_group_slug": ["Choose one of the six work families."]},
        )
    service = str(data.get("saved_service_slug", data.get("service")) or "").strip()
    service_record = SERVICE_BY_SLUG.get(service)
    if service and not service_record:
        raise ContractorPreferenceError(
            ["Choose a valid task."],
            {"saved_service_slug": ["Choose a task from the selected work family."]},
        )
    if service_record and family and service_record["group_slug"] != family:
        raise ContractorPreferenceError(
            ["Choose a task from the selected work family."],
            {"saved_service_slug": ["Choose a task from the selected work family."]},
        )
    if service_record and not family:
        family = service_record["group_slug"]
    sort = str(data.get("saved_sort", data.get("sort")) or DEFAULT_LEAD_SORT).strip()
    if sort not in set(sorts):
        raise ContractorPreferenceError(
            ["Choose a valid lead sort order."],
            {"saved_sort": ["Choose a valid lead sort order."]},
        )
    alert_preference = str(
        data.get("lead_alert_preference") or DEFAULT_LEAD_ALERT_PREFERENCE
    ).strip()
    if alert_preference not in LEAD_ALERT_VALUES:
        raise ContractorPreferenceError(
            ["Choose a valid lead alert preference."],
            {"lead_alert_preference": ["Choose Workdoe only or email alerts."]},
        )
    return {
        "saved_query": query,
        "saved_category": category,
        "saved_service_group_slug": family,
        "saved_service_slug": service,
        "saved_sort": sort,
        "lead_alert_preference": alert_preference,
    }


def availability_response(row) -> dict:
    status = row_value(row, "availability_status", DEFAULT_AVAILABILITY_STATUS)
    if status not in AVAILABILITY_STATUSES:
        status = DEFAULT_AVAILABILITY_STATUS
    available_from = str(row_value(row, "available_from", "") or "")
    labels = dict(AVAILABILITY_OPTIONS)
    label = labels[status]
    if available_from and status in {"limited", "unavailable"}:
        label = f"Taking new work from {available_from}"
    return {
        "status": status,
        "label": label,
        "available_from": available_from,
        "accepting_new_work": status != "unavailable",
        "self_reported": True,
    }


def contractor_preferences_response(row) -> dict:
    availability = availability_response(row)
    saved_family = str(row_value(row, "saved_service_group_slug", "") or "")
    saved_service = str(row_value(row, "saved_service_slug", "") or "")
    service_record = SERVICE_BY_SLUG.get(saved_service)
    if not service_record:
        saved_service = ""
    elif not saved_family:
        saved_family = service_record["group_slug"]
    family_record = GROUP_BY_SLUG.get(saved_family)
    alert_preference = str(
        row_value(row, "lead_alert_preference", DEFAULT_LEAD_ALERT_PREFERENCE)
        or DEFAULT_LEAD_ALERT_PREFERENCE
    )
    alert_consent_at = str(row_value(row, "lead_alert_consent_at", "") or "")
    if alert_preference not in LEAD_ALERT_VALUES or (
        alert_preference == "email" and not alert_consent_at
    ):
        alert_preference = DEFAULT_LEAD_ALERT_PREFERENCE
    return {
        "availability": availability,
        "availability_status": availability["status"],
        "available_from": availability["available_from"],
        "saved_query": str(row_value(row, "saved_query", "") or ""),
        "saved_category": str(row_value(row, "saved_category", "") or ""),
        "saved_service_group_slug": saved_family,
        "saved_family_label": family_record["name"] if family_record else "",
        "saved_service_slug": saved_service,
        "saved_service_label": service_record["name"] if service_record else "",
        "saved_sort": str(row_value(row, "saved_sort", DEFAULT_LEAD_SORT) or DEFAULT_LEAD_SORT),
        "has_saved_lead_view": bool(row_value(row, "saved_at")),
        "saved_at": str(row_value(row, "saved_at", "") or ""),
        "lead_alert_preference": alert_preference,
        "lead_alert_enabled": alert_preference == "email",
        "lead_alert_consent_at": alert_consent_at,
        "updated_at": str(row_value(row, "updated_at", "") or ""),
    }


def saved_lead_view_url(row, base_path: str = "/leads") -> str:
    preferences = contractor_preferences_response(row)
    if not preferences["has_saved_lead_view"]:
        return base_path
    params: dict[str, str] = {}
    if preferences["saved_service_group_slug"]:
        params["family"] = preferences["saved_service_group_slug"]
    if preferences["saved_service_slug"]:
        params["service"] = preferences["saved_service_slug"]
    if preferences["saved_category"]:
        params["category"] = preferences["saved_category"]
    if preferences["saved_query"]:
        params["q"] = preferences["saved_query"]
    if preferences["saved_sort"] != DEFAULT_LEAD_SORT:
        params["sort"] = preferences["saved_sort"]
    return base_path + (f"?{urlencode(params)}" if params else "")
