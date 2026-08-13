from __future__ import annotations

from urllib.parse import urlencode


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
    return {
        "category": category,
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
    if normalize_public_target(target) == "login":
        return "/login?" + urlencode({"next": f"/jobs/{job_id}"}, safe="/")
    return "/start?" + urlencode({"intent": "find-work", "job_id": str(job_id)})


def public_job_payload(row, target: str = "start") -> dict:
    job_id = row_value(row, "id")
    action_label = "Sign in" if normalize_public_target(target) == "login" else "Start"
    return {
        "id": job_id,
        "title": row_value(row, "title", ""),
        "category": row_value(row, "category", ""),
        "city": row_value(row, "city", ""),
        "state": row_value(row, "state", ""),
        "lat": row_value(row, "approx_lat"),
        "lng": row_value(row, "approx_lng"),
        "url": public_job_url(job_id, target),
        "action_label": action_label,
    }


def public_jobs_payload(
    rows: list,
    filters: dict[str, str],
    target: str = "start",
    view: str = "all",
) -> dict:
    map_jobs = [
        public_job_payload(row, target=target)
        for row in rows
        if has_public_coordinates(row)
    ]
    return {
        "count": len(map_jobs),
        "jobs": map_jobs,
        "filters": filters,
        "view": view,
        "location_privacy": PUBLIC_JOB_PRIVACY_NOTICE,
    }
