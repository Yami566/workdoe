from __future__ import annotations

from match_completions import completion_label, completion_state

BID_VIEWS = {"all", "pending", "approved", "rejected"}
DEFAULT_BID_VIEW = "all"
CONTRACTOR_BID_LIMIT = 100


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def normalize_contractor_bid_view(value: str | None) -> str:
    return value if value in BID_VIEWS else DEFAULT_BID_VIEW


def can_view_contractor_bids(user) -> bool:
    return bool(user) and row_value(user, "status") == "active" and row_value(user, "role") == "contractor"


def bid_thread_url(row) -> str:
    thread_id = row_value(row, "thread_id")
    return f"/messages/{thread_id}" if thread_id else ""


def contractor_bid_card(row) -> dict:
    status = row_value(row, "status", "") or ""
    thread_url = bid_thread_url(row)
    job_id = row_value(row, "job_id")
    card = {
        "id": row_value(row, "id"),
        "job_id": job_id,
        "title": row_value(row, "title", "") or "",
        "category": row_value(row, "category", "") or "",
        "service_slug": row_value(row, "service_slug", "") or "",
        "city": row_value(row, "city", "") or "",
        "state": row_value(row, "state", "") or "",
        "job_status": row_value(row, "job_status", "") or "",
        "close_reason": row_value(row, "close_reason", "") or "",
        "description": row_value(row, "description", "") or "",
        "desired_date": row_value(row, "desired_date", "") or "",
        "status": status,
        "scope_note": row_value(row, "scope_note", "") or "",
        "price_range": row_value(row, "price_range", "") or "",
        "timeline": row_value(row, "timeline", "") or "",
        "availability": row_value(row, "availability", "") or "",
        "created_at": row_value(row, "created_at", "") or "",
        "updated_at": row_value(row, "updated_at", "") or "",
        "thread_id": row_value(row, "thread_id"),
        "thread_url": thread_url,
        "client_confirmed_at": row_value(row, "client_confirmed_at", "") or "",
        "contractor_confirmed_at": row_value(row, "contractor_confirmed_at", "") or "",
        "verified_at": row_value(row, "verified_at", "") or "",
        "job_url": f"/jobs/{job_id}",
        "url": thread_url if status == "approved" and thread_url else f"/jobs/{job_id}",
        "row_cue": "Message" if status == "approved" and thread_url else "View",
    }
    card["completion_state"] = completion_state(card)
    card["completion_label"] = completion_label(card, "contractor")
    card["can_confirm_completion"] = (
        status == "approved"
        and card["job_status"] == "closed"
        and card["close_reason"] == "workdoe-match"
        and not card["contractor_confirmed_at"]
    )
    return card


def filter_contractor_bid_cards(cards: list[dict], view: str) -> list[dict]:
    normalized_view = normalize_contractor_bid_view(view)
    if normalized_view == "all":
        return list(cards)
    return [bid for bid in cards if bid["status"] == normalized_view]


def contractor_bid_stats(all_bids: list[dict], visible_bids: list[dict]) -> dict:
    return {
        "visible_requests": len(visible_bids),
        "total_requests": len(all_bids),
        "pending_requests": sum(1 for bid in all_bids if bid["status"] == "pending"),
        "approved_requests": sum(1 for bid in all_bids if bid["status"] == "approved"),
        "rejected_requests": sum(1 for bid in all_bids if bid["status"] == "rejected"),
        "verified_completions": sum(1 for bid in all_bids if bid["verified_at"]),
    }


def contractor_bid_view_links() -> list[dict[str, str]]:
    labels = {
        "all": "All",
        "pending": "Pending",
        "approved": "Approved",
        "rejected": "Rejected",
    }
    return [
        {
            "value": value,
            "label": labels[value],
            "url": "/contractor/dashboard" + (f"?bids={value}" if value != "all" else ""),
        }
        for value in ("all", "pending", "approved", "rejected")
    ]


def contractor_bids_payload(rows: list, view: str) -> dict:
    normalized_view = normalize_contractor_bid_view(view)
    all_bids = [contractor_bid_card(row) for row in rows]
    visible_bids = filter_contractor_bid_cards(all_bids, normalized_view)
    return {
        "ok": True,
        "view": normalized_view,
        "bids": visible_bids,
        "completed_work": [
            bid
            for bid in all_bids
            if bid["status"] == "approved"
            and bid["job_status"] == "closed"
            and bid["close_reason"] == "workdoe-match"
        ],
        "stats": contractor_bid_stats(all_bids, visible_bids),
        "view_links": contractor_bid_view_links(),
    }
