from __future__ import annotations

from contractor_reputation import contractor_reputation

MAX_COMPARISON_OFFERS = 4
COMPARISON_VIEWS = {"all", "pending"}
CREDENTIAL_FILTER_OPTIONS = (
    ("all", "All offers"),
    ("source-checked", "Source checked"),
    ("license-checked", "License record"),
)
CREDENTIAL_FILTERS = {value for value, _label in CREDENTIAL_FILTER_OPTIONS}


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def count_value(row, key: str) -> int:
    try:
        return max(0, int(row_value(row, key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def contractor_name(row) -> str:
    return (
        str(row_value(row, "business_name", "") or "").strip()
        or str(row_value(row, "company_name", "") or "").strip()
        or str(row_value(row, "display_name", "") or "").strip()
        or "Contractor"
    )


def years_active_label(row) -> str:
    raw_years = row_value(row, "years_in_business", None)
    years = count_value(row, "years_in_business")
    if raw_years in {None, ""}:
        return "Not provided"
    if years == 0:
        return "New business"
    return f"{years} year" if years == 1 else f"{years} years"


def count_label(count: int, singular: str, plural: str) -> str:
    if count == 0:
        return "None shown"
    return f"{count} {singular if count == 1 else plural}"


def normalize_credential_filter(value: str | None) -> str:
    return value if value in CREDENTIAL_FILTERS else "all"


def row_matches_credential_filter(row, credential_filter: str) -> bool:
    if credential_filter == "source-checked":
        return count_value(row, "source_checked_credential_count") > 0
    if credential_filter == "license-checked":
        return count_value(row, "source_checked_license_count") > 0
    return True


def offer_order_key(row) -> tuple[str, int]:
    created_at = str(row_value(row, "created_at", "") or "")
    try:
        request_id = int(row_value(row, "id", 0) or 0)
    except (TypeError, ValueError):
        request_id = 0
    return created_at, request_id


def comparison_offer(row, position: int, job_id: int = 0) -> dict:
    contractor_id = count_value(row, "contractor_id")
    profile_photo_id = count_value(row, "profile_photo_id")
    checked_credentials = count_value(row, "source_checked_credential_count")
    checked_licenses = count_value(row, "source_checked_license_count")
    verified_work = count_value(row, "verified_work_count")
    reputation = contractor_reputation(
        verified_work,
        checked_credentials,
        checked_licenses,
    )
    return {
        "id": count_value(row, "id"),
        "contractor_id": contractor_id,
        "offer_label": f"Offer {position}",
        "contractor_name": contractor_name(row),
        "trades": str(row_value(row, "trades", "") or "Contractor profile"),
        "profile_photo_url": (
            f"/media/contractors/{profile_photo_id}" if profile_photo_id else ""
        ),
        "profile_url": (
            f"/contractors/{contractor_id}?job_id={job_id}"
            if job_id > 0
            else f"/contractors/{contractor_id}"
        ),
        "price_range": str(row_value(row, "price_range", "") or "Not provided"),
        "timeline": str(row_value(row, "timeline", "") or "Not provided"),
        "availability": str(row_value(row, "availability", "") or "Not provided"),
        "scope_note": str(row_value(row, "scope_note", "") or "Not provided"),
        "experience": str(row_value(row, "experience", "") or "Not provided"),
        "questions": str(row_value(row, "questions", "") or ""),
        "reputation": reputation,
        "provider_facts": [
            {
                "key": "years-active",
                "label": "Years active",
                "value": years_active_label(row),
                "qualifier": "Self-reported",
            },
            {
                "key": "source-checked",
                "label": "Source checked",
                "value": count_label(
                    checked_credentials, "credential", "credentials"
                ),
                "qualifier": "Current records",
            },
            {
                "key": "license-source-checked",
                "label": "License record",
                "value": count_label(checked_licenses, "record", "records"),
                "qualifier": "Current public source",
            },
            {
                "key": "workdoe-completed",
                "label": "Workdoe-completed",
                "value": count_label(verified_work, "project", "projects"),
                "qualifier": "Both sides confirmed",
            },
            {
                "key": "insurance",
                "label": "Insurance",
                "value": (
                    "Self-reported"
                    if str(row_value(row, "insurance_status", "") or "").strip()
                    else "Not provided"
                ),
                "qualifier": "Not verified by Workdoe",
            },
        ],
    }


def bid_comparison(
    rows: list,
    view: str = "all",
    credential_filter: str = "all",
    job_id: int = 0,
) -> dict:
    normalized_filter = normalize_credential_filter(credential_filter)
    if view not in COMPARISON_VIEWS:
        all_pending_rows = []
    else:
        all_pending_rows = sorted(
            (
                row
                for row in rows
                if str(row_value(row, "status", "") or "") == "pending"
            ),
            key=offer_order_key,
        )
    pending_rows = [
        row
        for row in all_pending_rows
        if row_matches_credential_filter(row, normalized_filter)
    ][:MAX_COMPARISON_OFFERS]
    offers = [
        comparison_offer(row, position, job_id)
        for position, row in enumerate(pending_rows, start=1)
    ]
    filter_options = [
        {
            "value": value,
            "label": label,
            "count": sum(
                1
                for row in all_pending_rows
                if row_matches_credential_filter(row, value)
            ),
        }
        for value, label in CREDENTIAL_FILTER_OPTIONS
    ]
    return {
        "offers": offers,
        "count": len(offers),
        "has_multiple": len(offers) > 1,
        "pending_count": len(all_pending_rows),
        "credential_filter": normalized_filter,
        "credential_filter_options": filter_options,
        "order_label": "Received order",
        "ranking_effect": "none",
    }
