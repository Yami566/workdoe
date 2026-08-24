from __future__ import annotations

from urllib.parse import urlencode

from job_posts import bid_window, budget_label
from market_fit import annotate_job_fits
from project_readiness import project_brief_readiness
from service_taxonomy import GROUP_BY_SLUG, SERVICE_BY_SLUG

FILTER_QUERY_MAX_LENGTH = 80
DEFAULT_JOB_SORT = "newest"
DEFAULT_CONTRACTOR_LEAD_VIEW = "all"
CONTRACTOR_LEAD_LIMIT = 50
CONTRACTOR_LEAD_VIEWS = {"all", "new", "sent"}
JOB_SORTS = {"newest", "soonest", "city"}
JOB_CATEGORIES = {
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
}
CONTRACTOR_LEAD_PRIVACY_NOTICE = "Approximate city or ZIP-level pins only until a client approves a match."


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def first_query_value(params: dict, key: str, default: str = "") -> str:
    value = params.get(key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value or default)


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def parse_contractor_lead_limit(value: str | None, default: int = CONTRACTOR_LEAD_LIMIT) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, CONTRACTOR_LEAD_LIMIT))


def normalize_contractor_lead_view(value: str | None) -> str:
    return value if value in CONTRACTOR_LEAD_VIEWS else DEFAULT_CONTRACTOR_LEAD_VIEW


def normalize_contractor_lead_sort(value: str | None) -> str:
    return value if value in JOB_SORTS else DEFAULT_JOB_SORT


def contractor_lead_filters_from_query(params: dict) -> dict[str, str]:
    category = first_query_value(params, "category")
    if category not in JOB_CATEGORIES:
        category = ""
    family = compact_spaces(first_query_value(params, "family"))
    if family not in GROUP_BY_SLUG:
        family = ""
    service = compact_spaces(first_query_value(params, "service"))
    service_record = SERVICE_BY_SLUG.get(service)
    if not service_record or family and service_record["group_slug"] != family:
        service = ""
    elif not family:
        family = service_record["group_slug"]
    return {
        "category": category,
        "family": family,
        "service": service,
        "q": compact_spaces(first_query_value(params, "q"))[:FILTER_QUERY_MAX_LENGTH],
        "sort": normalize_contractor_lead_sort(first_query_value(params, "sort")),
    }


def contractor_lead_order_clause(sort: str) -> str:
    order_clauses = {
        "newest": "jobs.created_at DESC, jobs.id DESC",
        "soonest": (
            "CASE WHEN jobs.desired_date IS NULL OR jobs.desired_date = '' THEN 1 ELSE 0 END, "
            "jobs.desired_date ASC, jobs.created_at DESC, jobs.id DESC"
        ),
        "city": "jobs.city COLLATE NOCASE ASC, jobs.created_at DESC, jobs.id DESC",
    }
    return order_clauses[normalize_contractor_lead_sort(sort)]


def can_view_contractor_leads(user) -> bool:
    return bool(user) and row_value(user, "status") == "active" and row_value(user, "role") == "contractor"


def count_value(row, key: str) -> int:
    try:
        return int(row_value(row, key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def request_status(row) -> str:
    status = row_value(row, "request_status", "") or ""
    return status if status in {"pending", "approved", "rejected"} else ""


def has_map_coordinates(row) -> bool:
    return row_value(row, "approx_lat") is not None and row_value(row, "approx_lng") is not None


def contractor_lead_card(row) -> dict:
    job_id = row_value(row, "id")
    status = request_status(row)
    bidding = bid_window(row)
    return {
        "id": job_id,
        "title": row_value(row, "title", "") or "",
        "category": row_value(row, "category", "") or "",
        "service_group_slug": row_value(row, "service_group_slug", "") or "",
        "service_slug": row_value(row, "service_slug", "") or "",
        "city": row_value(row, "city", "") or "",
        "state": row_value(row, "state", "") or "",
        "description": row_value(row, "description", "") or "",
        "desired_date": row_value(row, "desired_date", "") or "",
        "license_preference": bool(
            int(row_value(row, "license_preference", 0) or 0)
        ),
        "created_at": row_value(row, "created_at", "") or "",
        "photo_count": count_value(row, "photo_count"),
        "budget": budget_label(row),
        "request_status": status,
        "bid_window": bidding,
        "url": f"/jobs/{job_id}",
        "can_request_match": not bool(status) and bidding["accepting"],
        "row_cue": "Sent" if status else ("View" if bidding["accepting"] else bidding["state"].title()),
        "fit_score": count_value(row, "fit_score"),
        "fit_label": row_value(row, "fit_label", "") or "",
        "brief_readiness": project_brief_readiness(row),
    }


def contractor_lead_map_marker(row) -> dict:
    status = request_status(row)
    bidding = bid_window(row)
    return {
        "id": row_value(row, "id"),
        "title": row_value(row, "title", "") or "",
        "category": row_value(row, "category", "") or "",
        "service_group_slug": row_value(row, "service_group_slug", "") or "",
        "service_slug": row_value(row, "service_slug", "") or "",
        "city": row_value(row, "city", "") or "",
        "state": row_value(row, "state", "") or "",
        "description": row_value(row, "description", "") or "",
        "desired_date": row_value(row, "desired_date", "") or "",
        "license_preference": bool(
            int(row_value(row, "license_preference", 0) or 0)
        ),
        "photo_count": count_value(row, "photo_count"),
        "budget": budget_label(row),
        "lat": row_value(row, "approx_lat"),
        "lng": row_value(row, "approx_lng"),
        "url": f"/jobs/{row_value(row, 'id')}",
        "detail_url": f"/jobs/{row_value(row, 'id')}",
        "action_label": "View bid status" if status else ("Review and bid" if bidding["accepting"] else "View bid status"),
        "request_status": status,
        "bid_window": bidding,
        "is_demo": False,
        "fit_score": count_value(row, "fit_score"),
        "fit_label": row_value(row, "fit_label", "") or "",
    }


def filter_contractor_lead_cards(cards: list[dict], view: str) -> list[dict]:
    normalized_view = normalize_contractor_lead_view(view)
    if normalized_view == "new":
        return [job for job in cards if not job["request_status"]]
    if normalized_view == "sent":
        return [job for job in cards if job["request_status"]]
    return list(cards)


def filter_map_markers(markers: list[dict], visible_jobs: list[dict]) -> list[dict]:
    visible_ids = {job["id"] for job in visible_jobs}
    return [marker for marker in markers if marker["id"] in visible_ids]


def contractor_lead_stats(all_jobs: list[dict], visible_jobs: list[dict]) -> dict:
    return {
        "visible_jobs": len(visible_jobs),
        "all_jobs": len(all_jobs),
        "new_jobs": sum(1 for job in all_jobs if not job["request_status"]),
        "sent_bids": sum(1 for job in all_jobs if job["request_status"]),
    }


def contractor_lead_view_links(filters: dict[str, str]) -> list[dict[str, str]]:
    labels = {"all": "All", "new": "New", "sent": "Sent"}
    links = []
    for value in ("all", "new", "sent"):
        args: dict[str, str] = {}
        if filters.get("category"):
            args["category"] = filters["category"]
        if filters.get("family"):
            args["family"] = filters["family"]
        if filters.get("service"):
            args["service"] = filters["service"]
        if filters.get("q"):
            args["q"] = filters["q"]
        if filters.get("sort", DEFAULT_JOB_SORT) != DEFAULT_JOB_SORT:
            args["sort"] = filters["sort"]
        if value != "all":
            args["view"] = value
        links.append(
            {
                "value": value,
                "label": labels[value],
                "url": "/leads" + (f"?{urlencode(args)}" if args else ""),
            }
        )
    return links


def contractor_leads_payload(
    rows: list,
    filters: dict[str, str],
    view: str,
    service_slugs=None,
    service_zone_slugs=None,
) -> dict:
    normalized_view = normalize_contractor_lead_view(view)
    annotated_rows = annotate_job_fits(
        rows,
        service_slugs or [],
        service_zone_slugs or [],
    )
    all_jobs = [contractor_lead_card(row) for row in annotated_rows]
    visible_jobs = filter_contractor_lead_cards(all_jobs, normalized_view)
    all_markers = [
        contractor_lead_map_marker(row)
        for row in annotated_rows
        if has_map_coordinates(row)
    ]
    map_jobs = filter_map_markers(all_markers, visible_jobs)
    return {
        "ok": True,
        "view": normalized_view,
        "count": len(map_jobs),
        "jobs": visible_jobs,
        "map_jobs": map_jobs,
        "filters": filters,
        "stats": contractor_lead_stats(all_jobs, visible_jobs),
        "view_links": contractor_lead_view_links(filters),
        "location_privacy": CONTRACTOR_LEAD_PRIVACY_NOTICE,
    }
