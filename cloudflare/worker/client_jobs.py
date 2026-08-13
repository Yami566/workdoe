from __future__ import annotations


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
    return {
        "id": job_id,
        "title": row_value(row, "title", "") or "",
        "category": row_value(row, "category", "") or "",
        "city": row_value(row, "city", "") or "",
        "state": row_value(row, "state", "") or "",
        "zip_code": row_value(row, "zip_code", "") or "",
        "description": row_value(row, "description", "") or "",
        "desired_date": row_value(row, "desired_date", "") or "",
        "status": status,
        "created_at": row_value(row, "created_at", "") or "",
        "updated_at": row_value(row, "updated_at", "") or "",
        "request_count": count_value(row, "request_count"),
        "pending_count": pending_count,
        "approved_count": count_value(row, "approved_count"),
        "rejected_count": count_value(row, "rejected_count"),
        "url": review_url if needs_review else detail_url,
        "detail_url": detail_url,
        "review_url": review_url,
        "edit_url": f"/client/jobs/{job_id}/edit",
        "can_close": status == "open",
        "can_reopen": status == "closed",
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
        for value in ("all", "open", "review", "closed")
    ]


def client_jobs_payload(rows: list, view: str) -> dict:
    normalized_view = normalize_client_job_view(view)
    all_jobs = [client_job_card(row) for row in rows]
    visible_jobs = filter_client_job_cards(all_jobs, normalized_view)
    return {
        "ok": True,
        "view": normalized_view,
        "jobs": visible_jobs,
        "stats": client_job_stats(all_jobs, visible_jobs),
        "view_links": client_job_view_links(),
    }
