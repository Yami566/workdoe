from __future__ import annotations

from job_posts import bid_window, budget_label, project_setting_label
from project_readiness import project_brief_readiness

JOB_DETAIL_PRIVACY_NOTICE = (
    "Contractors see city/state and ZIP prefix only until a client approves a match."
)


class JobDetailError(ValueError):
    pass


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def parse_job_detail_id(path: str) -> int:
    prefix = "/api/jobs/"
    if not path.startswith(prefix):
        raise JobDetailError("Unsupported job detail route.")
    raw_id = path[len(prefix) :].strip("/")
    if not raw_id.isdigit() or int(raw_id) < 1:
        raise JobDetailError("Unsupported job detail route.")
    return int(raw_id)


def zip_prefix(zip_code: str | None) -> str:
    digits = "".join(ch for ch in str(zip_code or "") if ch.isdigit())
    return f"{digits[:3]}xx" if len(digits) >= 3 else ""


def can_view_job_detail(user, job) -> bool:
    if not user or not job:
        return False
    if row_value(user, "status") != "active":
        return False
    role = row_value(user, "role")
    if role == "admin":
        return True
    if role == "client":
        return row_value(job, "client_id") == row_value(user, "id")
    if role == "contractor":
        return (
            row_value(job, "client_status") == "active"
            and row_value(job, "status") != "hidden"
        )
    return False


def viewer_kind(user, job) -> str:
    if row_value(user, "role") == "admin":
        return "admin"
    if row_value(user, "role") == "client" and row_value(job, "client_id") == row_value(user, "id"):
        return "owner"
    if row_value(user, "role") == "contractor":
        return "contractor"
    return "unknown"


def job_detail_payload(
    user,
    job,
    photos: list[dict] | None = None,
    existing_request: dict | None = None,
    scope_answer_count: int | None = None,
) -> dict:
    viewer = viewer_kind(user, job)
    owner_view = viewer in {"owner", "admin"}
    bidding = bid_window(job)
    payload = {
        "ok": True,
        "viewer": viewer,
        "job": {
            "id": row_value(job, "id"),
            "title": row_value(job, "title", ""),
            "category": row_value(job, "category", ""),
            "service_slug": row_value(job, "service_slug", ""),
            "project_setting": row_value(job, "project_setting", ""),
            "license_preference": bool(
                int(row_value(job, "license_preference", 0) or 0)
            ),
            "project_setting_label": project_setting_label(
                row_value(job, "project_setting", "")
            ),
            "city": row_value(job, "city", ""),
            "state": row_value(job, "state", ""),
            "area_label": area_label(job, owner_view=owner_view),
            "description": row_value(job, "description", ""),
            "desired_date": row_value(job, "desired_date", "") or "",
            "budget": budget_label(job),
            "status": row_value(job, "status", ""),
            "close_reason": row_value(job, "close_reason", "") or "",
            "closed_at": row_value(job, "closed_at", "") or "",
            "photo_count": len(photos or []),
            "brief_readiness": project_brief_readiness(
                job,
                scope_answer_count=scope_answer_count,
                photo_count=len(photos or []),
            ),
            "location_privacy": JOB_DETAIL_PRIVACY_NOTICE,
            "bid_window": bidding,
            "can_request_match": viewer == "contractor" and bidding["accepting"] and not existing_request,
        },
        "photos": [job_photo_payload(photo, owner_view=owner_view) for photo in photos or []],
    }
    if owner_view:
        payload["job"]["zip_code"] = row_value(job, "zip_code", "")
        payload["job"]["close_note"] = row_value(job, "close_note", "") or ""
    else:
        payload["job"]["zip_prefix"] = zip_prefix(row_value(job, "zip_code", ""))
    if existing_request:
        payload["existing_request"] = contractor_request_payload(existing_request)
    return payload


def area_label(job, owner_view: bool = False) -> str:
    city = row_value(job, "city", "")
    state = row_value(job, "state", "")
    zip_value = row_value(job, "zip_code", "") if owner_view else zip_prefix(row_value(job, "zip_code", ""))
    return ", ".join(part for part in (city, state) if part) + (f" {zip_value}" if zip_value else "")


def job_photo_payload(photo, owner_view: bool = False) -> dict:
    payload = {
        "id": row_value(photo, "id"),
        "url": f"/media/jobs/{row_value(photo, 'id')}",
        "original_filename": row_value(photo, "original_filename", ""),
    }
    if owner_view:
        payload["is_hidden"] = row_value(photo, "is_hidden", 0)
    return payload


def contractor_request_payload(match_request) -> dict:
    payload = {
        "id": row_value(match_request, "id"),
        "status": row_value(match_request, "status"),
        "scope_note": row_value(match_request, "scope_note", ""),
        "price_range": row_value(match_request, "price_range", ""),
        "timeline": row_value(match_request, "timeline", ""),
        "availability": row_value(match_request, "availability", ""),
    }
    thread_id = row_value(match_request, "thread_id")
    if thread_id:
        payload["thread_id"] = thread_id
        payload["thread_url"] = f"/messages/{thread_id}"
    return payload
