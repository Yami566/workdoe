from __future__ import annotations

from urllib.parse import urlencode

from bid_comparison import bid_comparison, normalize_credential_filter
from job_posts import bid_window
from match_completions import completion_label, completion_state

CLIENT_REQUEST_VIEWS = {"all", "pending", "approved", "rejected"}
DEFAULT_CLIENT_REQUEST_VIEW = "all"
CLIENT_REQUEST_LIMIT = 100


class ClientRequestError(ValueError):
    pass


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def parse_client_job_requests_path(path: str) -> int:
    prefix = "/api/client/jobs/"
    suffix = "/requests"
    if not path.startswith(prefix) or not path.endswith(suffix):
        raise ClientRequestError("Unsupported client request route.")
    raw_id = path[len(prefix) : -len(suffix)].strip("/")
    if not raw_id.isdigit() or int(raw_id) < 1:
        raise ClientRequestError("Unsupported client request route.")
    return int(raw_id)


def normalize_client_request_view(value: str | None) -> str:
    return value if value in CLIENT_REQUEST_VIEWS else DEFAULT_CLIENT_REQUEST_VIEW


def can_view_client_job_requests(user, job) -> bool:
    if not user or not job:
        return False
    if row_value(user, "status") != "active":
        return False
    if row_value(user, "role") == "admin":
        return True
    return row_value(user, "role") == "client" and row_value(user, "id") == row_value(job, "client_id")


def contractor_name(row) -> str:
    return (
        row_value(row, "business_name", "")
        or row_value(row, "company_name", "")
        or row_value(row, "display_name", "")
        or "Contractor"
    )


def thread_url(row) -> str:
    thread_id = row_value(row, "thread_id")
    return f"/messages/{thread_id}" if thread_id else ""


def client_request_card(row) -> dict:
    status = row_value(row, "status", "") or ""
    contractor_id = row_value(row, "contractor_id")
    thread_link = thread_url(row)
    card = {
        "id": row_value(row, "id"),
        "job_id": row_value(row, "job_id"),
        "contractor_id": contractor_id,
        "contractor_name": contractor_name(row),
        "display_name": row_value(row, "display_name", "") or "",
        "company_name": row_value(row, "company_name", "") or "",
        "business_name": row_value(row, "business_name", "") or "",
        "trades": row_value(row, "trades", "") or "Contractor profile",
        "status": status,
        "scope_note": row_value(row, "scope_note", "") or "",
        "price_range": row_value(row, "price_range", "") or "",
        "timeline": row_value(row, "timeline", "") or "",
        "experience": row_value(row, "experience", "") or "",
        "questions": row_value(row, "questions", "") or "",
        "availability": row_value(row, "availability", "") or "",
        "created_at": row_value(row, "created_at", "") or "",
        "updated_at": row_value(row, "updated_at", "") or "",
        "thread_id": row_value(row, "thread_id"),
        "thread_url": thread_link,
        "profile_url": f"/contractors/{contractor_id}",
        "client_confirmed_at": row_value(row, "client_confirmed_at", "") or "",
        "contractor_confirmed_at": row_value(row, "contractor_confirmed_at", "") or "",
        "verified_at": row_value(row, "verified_at", "") or "",
        "can_approve": status == "pending",
        "can_reject": status == "pending",
        "needs_review": status == "pending",
        "row_cue": "Message" if status == "approved" and thread_link else "Review",
        "source_checked_credential_count": int(
            row_value(row, "source_checked_credential_count", 0) or 0
        ),
        "source_checked_license_count": int(
            row_value(row, "source_checked_license_count", 0) or 0
        ),
        "verified_work_count": int(row_value(row, "verified_work_count", 0) or 0),
    }
    card["completion_state"] = completion_state(card)
    card["completion_label"] = completion_label(card, "client")
    return card


def filter_client_request_cards(cards: list[dict], view: str) -> list[dict]:
    normalized_view = normalize_client_request_view(view)
    if normalized_view == "all":
        return list(cards)
    return [request for request in cards if request["status"] == normalized_view]


def client_request_stats(all_requests: list[dict], visible_requests: list[dict]) -> dict:
    return {
        "visible": len(visible_requests),
        "total": len(all_requests),
        "pending": sum(1 for request in all_requests if request["status"] == "pending"),
        "approved": sum(1 for request in all_requests if request["status"] == "approved"),
        "rejected": sum(1 for request in all_requests if request["status"] == "rejected"),
        "verified": sum(1 for request in all_requests if request["verified_at"]),
    }


def client_request_view_links(
    job_id: int,
    credential_filter: str = "all",
) -> list[dict[str, str]]:
    labels = {
        "all": "All",
        "pending": "Pending",
        "approved": "Approved",
        "rejected": "Rejected",
    }
    links = []
    for value in ("all", "pending", "approved", "rejected"):
        args = {"bids": value} if value != "all" else {}
        if credential_filter != "all":
            args["credentials"] = credential_filter
        query = f"?{urlencode(args)}" if args else ""
        links.append(
            {
                "value": value,
                "label": labels[value],
                "url": f"/client/jobs/{job_id}{query}#mini-bids",
            }
        )
    return links


def comparison_filter_links(
    job_id: int,
    view: str,
    options: list[dict],
) -> list[dict]:
    links = []
    for option in options:
        value = option["value"]
        args = {}
        if view != "all":
            args["bids"] = view
        if value != "all":
            args["credentials"] = value
        query = f"?{urlencode(args)}" if args else ""
        links.append(
            {
                **option,
                "url": f"/client/jobs/{job_id}{query}#mini-bids",
            }
        )
    return links


def client_job_requests_payload(
    job,
    rows: list,
    view: str,
    credential_filter: str = "all",
) -> dict:
    job_id = row_value(job, "id")
    normalized_view = normalize_client_request_view(view)
    normalized_filter = normalize_credential_filter(credential_filter)
    all_requests = [client_request_card(row) for row in rows]
    visible_requests = filter_client_request_cards(all_requests, normalized_view)
    bidding = bid_window(job, len(all_requests))
    comparison = bid_comparison(rows, normalized_view, normalized_filter)
    comparison["credential_filter_options"] = comparison_filter_links(
        job_id,
        normalized_view,
        comparison["credential_filter_options"],
    )
    return {
        "ok": True,
        "view": normalized_view,
        "job": {
            "id": job_id,
            "title": row_value(job, "title", "") or "",
            "status": row_value(job, "status", "") or "",
            "bid_window": bidding,
            "url": f"/client/jobs/{job_id}",
        },
        "requests": visible_requests,
        "comparison": comparison,
        "stats": client_request_stats(all_requests, visible_requests),
        "view_links": client_request_view_links(job_id, normalized_filter),
    }
