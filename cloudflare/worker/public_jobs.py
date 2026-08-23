from __future__ import annotations

from urllib.parse import urlencode

from job_posts import budget_label
from service_taxonomy import GROUP_BY_SLUG, SERVICE_BY_SLUG, service_label

FILTER_QUERY_MAX_LENGTH = 80
DEFAULT_JOB_SORT = "newest"
PUBLIC_JOB_PRIVACY_NOTICE = "Approximate city or ZIP-level pins only."
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
JOB_SORTS = {"newest", "soonest", "city"}


def first_query_value(params: dict, key: str, default: str = "") -> str:
    value = params.get(key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value or default)


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def parse_public_limit(value: str | None, default: int = 24, maximum: int = 50) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def normalize_public_sort(value: str | None) -> str:
    return value if value in JOB_SORTS else DEFAULT_JOB_SORT


def normalize_public_target(value: str | None) -> str:
    return value if value in {"login", "start"} else "start"


def public_job_filters_from_query(params: dict) -> dict[str, str]:
    category = first_query_value(params, "category")
    if category not in JOB_CATEGORIES:
        category = ""
    family = compact_spaces(first_query_value(params, "family"))
    if family not in GROUP_BY_SLUG:
        family = ""
    service = compact_spaces(first_query_value(params, "service"))
    selected_service = SERVICE_BY_SLUG.get(service)
    if not selected_service or family and selected_service["group_slug"] != family:
        service = ""
    elif not family:
        family = selected_service["group_slug"]
    return {
        "category": category,
        "family": family,
        "service": service,
        "q": compact_spaces(first_query_value(params, "q"))[:FILTER_QUERY_MAX_LENGTH],
        "sort": normalize_public_sort(first_query_value(params, "sort")),
    }


def public_job_order_clause(sort: str) -> str:
    order_clauses = {
        "newest": "jobs.created_at DESC, jobs.id DESC",
        "soonest": (
            "CASE WHEN jobs.desired_date IS NULL OR jobs.desired_date = '' THEN 1 ELSE 0 END, "
            "jobs.desired_date ASC, jobs.created_at DESC, jobs.id DESC"
        ),
        "city": "jobs.city COLLATE NOCASE ASC, jobs.created_at DESC, jobs.id DESC",
    }
    return order_clauses[normalize_public_sort(sort)]


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def has_public_coordinates(row) -> bool:
    return row_value(row, "approx_lat") is not None and row_value(row, "approx_lng") is not None


def public_job_url(job_id, target: str) -> str:
    job_id_text = str(job_id or "")
    if job_id_text.startswith("demo-"):
        args = {"intent": "find-work", "demo": job_id_text}
        return "/login?" + urlencode({"next": "/?" + urlencode({"job_id": job_id_text})}, safe="/?=") if normalize_public_target(target) == "login" else "/create-account?" + urlencode(args)
    if normalize_public_target(target) == "login":
        return "/login?" + urlencode({"next": f"/jobs/{job_id}"}, safe="/")
    return "/create-account?" + urlencode({"intent": "find-work", "job_id": str(job_id)})


def public_job_payload(row, target: str = "start") -> dict:
    job_id = row_value(row, "id")
    is_demo = bool(row_value(row, "is_demo", False))
    action_label = "Sign in" if normalize_public_target(target) == "login" else "Create account to respond"
    payload = {
        "id": job_id,
        "title": row_value(row, "title", ""),
        "category": row_value(row, "category", ""),
        "service_group_slug": row_value(row, "service_group_slug", ""),
        "service_slug": row_value(row, "service_slug", ""),
        "service_name": service_label(
            row_value(row, "service_slug", ""), row_value(row, "category", "")
        ),
        "city": row_value(row, "city", ""),
        "state": row_value(row, "state", ""),
        "budget": budget_label(row),
        "desired_date": row_value(row, "desired_date", "") or "",
        "photo_count": int(row_value(row, "photo_count", 0) or 0),
        "lat": row_value(row, "approx_lat"),
        "lng": row_value(row, "approx_lng"),
        "url": public_job_url(job_id, target),
        "detail_url": "/?" + urlencode({"job_id": str(job_id)}),
        "action_label": action_label,
        "is_demo": is_demo,
        "sample_label": "Sample project" if is_demo else "Open project",
    }
    if is_demo:
        payload["description"] = row_value(row, "description", "")
    return payload


def public_jobs_payload(
    rows: list,
    filters: dict[str, str],
    target: str = "start",
    view: str = "all",
    *,
    viewport: dict[str, float] | None = None,
    next_cursor: str = "",
    truncated: bool = False,
) -> dict:
    map_jobs = [
        public_job_payload(row, target=target)
        for row in rows
        if has_public_coordinates(row)
    ]
    demo_count = sum(1 for job in map_jobs if job["is_demo"])
    return {
        "count": len(map_jobs),
        "result_count": len(map_jobs),
        "jobs": map_jobs,
        "next_cursor": next_cursor,
        "truncated": bool(truncated),
        "viewport": viewport,
        "demo_count": demo_count,
        "live_count": len(map_jobs) - demo_count,
        "filters": filters,
        "view": view,
        "location_privacy": PUBLIC_JOB_PRIVACY_NOTICE,
    }
