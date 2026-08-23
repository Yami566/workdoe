from __future__ import annotations

from job_posts import bid_window, budget_label
from project_readiness import project_brief_readiness

PROJECT_CLOSE_REASON_LABELS = {
    "workdoe-match": "Hired through Workdoe",
    "hired-elsewhere": "Hired elsewhere",
    "plans-changed": "Plans changed",
    "no-qualified-bid": "No bid fit",
    "scope-changed": "Scope changed",
    "duplicate": "Duplicate post",
    "other": "Other",
}


CLIENT_JOB_VIEWS = {"all", "open", "review", "closed"}
DEFAULT_CLIENT_JOB_VIEW = "all"
CLIENT_JOB_LIMIT = 100


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def normalize_client_job_view(value: str | None) -> str:
    return value if value in CLIENT_JOB_VIEWS else DEFAULT_CLIENT_JOB_VIEW


def can_view_client_jobs(user) -> bool:
    return bool(user) and row_value(user, "status") == "active" and row_value(user, "role") == "client"


def count_value(row, key: str) -> int:
    try:
        return int(row_value(row, key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def client_job_card(row) -> dict:
    job_id = row_value(row, "id")
    pending_count = count_value(row, "pending_count")
    status = row_value(row, "status", "")
    detail_url = f"/client/jobs/{job_id}"
    review_url = f"{detail_url}?bids=pending#mini-bids"
    needs_review = pending_count > 0
    verified_completion_count = count_value(row, "verified_completion_count")
    completion_signal_count = count_value(row, "completion_signal_count")
    bidding = bid_window(row)
    repeat_match_request_id = count_value(row, "repeat_match_request_id")
    repeat_contractor_name = str(
        row_value(row, "repeat_contractor_name", "") or ""
    )
    brief_readiness = project_brief_readiness(row)
    return {
        "id": job_id,
        "title": row_value(row, "title", "") or "",
        "category": row_value(row, "category", "") or "",
        "service_slug": row_value(row, "service_slug", "") or "",
        "city": row_value(row, "city", "") or "",
        "state": row_value(row, "state", "") or "",
        "zip_code": row_value(row, "zip_code", "") or "",
        "description": row_value(row, "description", "") or "",
        "desired_date": row_value(row, "desired_date", "") or "",
        "budget": budget_label(row),
        "status": status,
        "close_reason": row_value(row, "close_reason", "") or "",
        "close_reason_label": PROJECT_CLOSE_REASON_LABELS.get(
            row_value(row, "close_reason", "") or "",
            "Closed",
        ),
        "created_at": row_value(row, "created_at", "") or "",
        "updated_at": row_value(row, "updated_at", "") or "",
        "request_count": count_value(row, "request_count"),
        "bid_window": bidding,
        "pending_count": pending_count,
        "approved_count": count_value(row, "approved_count"),
        "rejected_count": count_value(row, "rejected_count"),
        "verified_completion_count": verified_completion_count,
        "completion_signal_count": completion_signal_count,
        "brief_readiness": brief_readiness,
        "url": review_url if needs_review else detail_url,
        "detail_url": detail_url,
        "review_url": review_url,
        "edit_url": f"/client/jobs/{job_id}/edit",
        "repeat_url": f"/jobs/new?repeat={job_id}",
        "repeat_match_request_id": repeat_match_request_id,
        "repeat_contractor_name": repeat_contractor_name,
        "repeat_invite_url": (
            f"/jobs/new?repeat={job_id}&invite={repeat_match_request_id}"
            if repeat_match_request_id and repeat_contractor_name
            else ""
        ),
        "can_close": status == "open",
        "can_reopen": status == "closed" and completion_signal_count == 0,
        "can_extend_bids": bidding["can_extend"],
        "needs_review": needs_review,
        "row_cue": "Review bids" if needs_review else "Review",
    }


def filter_client_job_cards(cards: list[dict], view: str) -> list[dict]:
    if view == "review":
        return [job for job in cards if job["pending_count"] > 0]
    if view == "open":
        return [job for job in cards if job["status"] == "open"]
    if view == "closed":
        return [job for job in cards if job["status"] == "closed"]
    return list(cards)


def client_job_stats(all_jobs: list[dict], visible_jobs: list[dict]) -> dict:
    return {
        "visible_jobs": len(visible_jobs),
        "total_jobs": len(all_jobs),
        "open_jobs": sum(1 for job in all_jobs if job["status"] == "open"),
        "closed_jobs": sum(1 for job in all_jobs if job["status"] == "closed"),
        "review_jobs": sum(1 for job in all_jobs if job["pending_count"] > 0),
        "pending_requests": sum(job["pending_count"] for job in all_jobs),
        "approved_requests": sum(job["approved_count"] for job in all_jobs),
        "rejected_requests": sum(job["rejected_count"] for job in all_jobs),
        "verified_completions": sum(
            job["verified_completion_count"] for job in all_jobs
        ),
        "brief_ready_jobs": sum(
            1 for job in all_jobs if job["brief_readiness"]["state"] == "ready"
        ),
    }


def client_job_view_links() -> list[dict[str, str]]:
    labels = {
        "all": "All",
        "open": "Open",
        "review": "Review",
        "closed": "Closed",
    }
    return [
        {
            "value": value,
            "label": labels[value],
            "url": "/client/dashboard" + (f"?view={value}" if value != "all" else ""),
        }
        for value in ("all", "review", "open", "closed")
    ]


def client_jobs_payload(rows: list, view: str) -> dict:
    normalized_view = normalize_client_job_view(view)
    all_jobs = [client_job_card(row) for row in rows]
    visible_jobs = filter_client_job_cards(all_jobs, normalized_view)
    return {
        "ok": True,
        "view": normalized_view,
        "jobs": visible_jobs,
        "history": [job for job in all_jobs if job["status"] == "closed"],
        "stats": client_job_stats(all_jobs, visible_jobs),
        "view_links": client_job_view_links(),
    }
