from __future__ import annotations

MAX_COMPARISON_OFFERS = 4
COMPARISON_VIEWS = {"all", "pending"}


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


def offer_order_key(row) -> tuple[str, int]:
    created_at = str(row_value(row, "created_at", "") or "")
    try:
        request_id = int(row_value(row, "id", 0) or 0)
    except (TypeError, ValueError):
        request_id = 0
    return created_at, request_id


def comparison_offer(row, position: int) -> dict:
    contractor_id = count_value(row, "contractor_id")
    checked_credentials = count_value(row, "source_checked_credential_count")
    verified_work = count_value(row, "verified_work_count")
    return {
        "id": count_value(row, "id"),
        "contractor_id": contractor_id,
        "offer_label": f"Offer {position}",
        "contractor_name": contractor_name(row),
        "trades": str(row_value(row, "trades", "") or "Contractor profile"),
        "profile_url": f"/contractors/{contractor_id}",
        "price_range": str(row_value(row, "price_range", "") or "Not provided"),
        "timeline": str(row_value(row, "timeline", "") or "Not provided"),
        "availability": str(row_value(row, "availability", "") or "Not provided"),
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


def bid_comparison(rows: list, view: str = "all") -> dict:
    if view not in COMPARISON_VIEWS:
        pending_rows = []
    else:
        pending_rows = sorted(
            (
                row
                for row in rows
                if str(row_value(row, "status", "") or "") == "pending"
            ),
            key=offer_order_key,
        )[:MAX_COMPARISON_OFFERS]
    offers = [
        comparison_offer(row, position)
        for position, row in enumerate(pending_rows, start=1)
    ]
    return {
        "offers": offers,
        "count": len(offers),
        "has_multiple": len(offers) > 1,
        "order_label": "Received order",
    }
