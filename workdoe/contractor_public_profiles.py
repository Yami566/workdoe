from __future__ import annotations


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default


def contractor_choice_context(viewer, contractor_id: int, relationship) -> dict | None:
    if (
        not viewer
        or row_value(viewer, "role") != "client"
        or row_value(viewer, "status") != "active"
        or not relationship
    ):
        return None
    try:
        viewer_id = int(row_value(viewer, "id", 0) or 0)
        client_id = int(row_value(relationship, "client_id", 0) or 0)
        related_contractor_id = int(
            row_value(relationship, "contractor_id", 0) or 0
        )
        job_id = int(row_value(relationship, "job_id", 0) or 0)
        request_id = int(row_value(relationship, "request_id", 0) or 0)
        thread_id = int(row_value(relationship, "thread_id", 0) or 0)
    except (TypeError, ValueError):
        return None
    if (
        viewer_id < 1
        or viewer_id != client_id
        or related_contractor_id != contractor_id
        or job_id < 1
        or request_id < 1
    ):
        return None
    status = str(row_value(relationship, "status", "") or "")
    return {
        "job_id": job_id,
        "job_title": str(
            row_value(relationship, "job_title", "Project") or "Project"
        ),
        "request_id": request_id,
        "status": status,
        "back_url": f"/client/jobs/{job_id}#mini-bids",
        "can_choose": status == "pending",
        "thread_url": f"/messages/{thread_id}" if status == "approved" and thread_id else "",
    }
