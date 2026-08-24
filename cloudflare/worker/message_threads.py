from __future__ import annotations

from contractor_reputation import contractor_match_provider

MESSAGE_BODY_MAX_LENGTH = 1000
MAX_MESSAGE_BODY_BYTES = 4096
MESSAGE_BODY_TOO_LONG = "Keep messages under 1000 characters."
MESSAGE_THREAD_VIEW_OPTIONS = ("all", "reply", "unread")


class MessageThreadError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        self.field_errors = message_thread_field_errors(errors)
        super().__init__("; ".join(errors))


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def count_value(row, key: str) -> int:
    try:
        return max(0, int(row_value(row, key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def normalize_message_thread_view(value: str | None) -> str:
    return value if value in MESSAGE_THREAD_VIEW_OPTIONS else "all"


def parse_thread_id(path: str) -> int:
    prefix = "/api/messages/threads/"
    if not path.startswith(prefix):
        raise MessageThreadError(["Unsupported message thread route."])
    raw_id = path[len(prefix) :].strip("/")
    if not raw_id.isdigit() or int(raw_id) < 1:
        raise MessageThreadError(["Unsupported message thread route."])
    return int(raw_id)


def can_view_thread(user, thread) -> bool:
    if not user or not thread:
        return False
    if row_value(user, "status") != "active":
        return False
    if row_value(user, "role") == "admin":
        return True
    user_id = row_value(user, "id")
    return user_id in {row_value(thread, "client_id"), row_value(thread, "contractor_id")}


def can_send_thread_message(user, thread) -> bool:
    if not can_view_thread(user, thread):
        return False
    if row_value(user, "role") not in {"client", "contractor"}:
        return False
    user_id = row_value(user, "id")
    return user_id in {row_value(thread, "client_id"), row_value(thread, "contractor_id")}


def cleaned_message_payload(payload: dict) -> str:
    if not isinstance(payload, dict):
        raise MessageThreadError(["Message payload must be a JSON object."])
    return (payload.get("body") or "").strip()


def message_body_payload(payload: dict) -> str:
    body = cleaned_message_payload(payload)
    if not body:
        raise MessageThreadError(["Write a message before sending."])
    if len(body) > MESSAGE_BODY_MAX_LENGTH:
        raise MessageThreadError([MESSAGE_BODY_TOO_LONG])
    return body


def message_thread_field_errors(errors: list[str]) -> dict[str, list[str]]:
    return {"body": [error for error in errors if message_thread_error_field(error) == "body"]}


def message_thread_error_field(message: str) -> str:
    if "message" in message or "1000" in message:
        return "body"
    return ""


def message_thread_summary(row, viewer_id: int | None = None) -> dict:
    unread_count = count_value(row, "unread_count")
    if viewer_id is None:
        needs_reply = bool(row_value(row, "needs_reply", False))
    else:
        last_sender_id = count_value(row, "last_sender_id")
        needs_reply = bool(count_value(row, "last_message_id") and last_sender_id) and (
            last_sender_id != viewer_id
        )
    job_id = row_value(row, "job_id")
    contractor_id = row_value(row, "contractor_id")
    contractor_name = row_value(row, "contractor_name")
    return {
        "id": row_value(row, "id"),
        "job_id": job_id,
        "title": row_value(row, "title"),
        "category": row_value(row, "category"),
        "service_slug": row_value(row, "service_slug", ""),
        "city": row_value(row, "city"),
        "state": row_value(row, "state"),
        "price_range": row_value(row, "price_range", "") or "",
        "timeline": row_value(row, "timeline", "") or "",
        "availability": row_value(row, "availability", "") or "",
        "client_name": row_value(row, "client_name"),
        "contractor_name": contractor_name,
        "provider": contractor_match_provider(
            contractor_id,
            contractor_name,
            job_id,
            row_value(row, "verified_completion_count", 0),
            row_value(row, "source_checked_credential_count", 0),
            row_value(row, "source_checked_license_count", 0),
        ),
        "last_message": row_value(row, "last_message", "") or "",
        "last_message_at": row_value(row, "last_message_at", "") or "",
        "message_count": count_value(row, "message_count"),
        "unread_count": unread_count,
        "has_unread": unread_count > 0,
        "needs_reply": needs_reply,
        "url": f"/messages/{row_value(row, 'id')}",
    }


def message_threads_listing_payload(
    rows: list[dict],
    view: str | None = None,
    viewer_id: int | None = None,
) -> dict:
    thread_view = normalize_message_thread_view(view)
    summaries = [message_thread_summary(thread, viewer_id) for thread in rows]
    if thread_view == "reply":
        visible_threads = [thread for thread in summaries if thread["needs_reply"]]
    elif thread_view == "unread":
        visible_threads = [thread for thread in summaries if thread["has_unread"]]
    else:
        visible_threads = summaries
    return {
        "ok": True,
        "view": thread_view,
        "threads": visible_threads,
        "stats": {
            "threads": len(summaries),
            "messages": sum(thread["message_count"] for thread in summaries),
            "unread": sum(thread["unread_count"] for thread in summaries),
            "unread_threads": sum(1 for thread in summaries if thread["has_unread"]),
            "reply_threads": sum(1 for thread in summaries if thread["needs_reply"]),
        },
    }


def message_detail_payload(message) -> dict:
    return {
        "id": row_value(message, "id"),
        "sender_id": row_value(message, "sender_id"),
        "sender_name": row_value(message, "display_name"),
        "body": row_value(message, "body"),
        "is_hidden": row_value(message, "is_hidden", 0),
        "created_at": row_value(message, "created_at"),
    }


def thread_detail_payload(thread, messages: list[dict]) -> dict:
    return {
        "ok": True,
        "thread": message_thread_summary({**dict(thread), "message_count": len(messages)} if isinstance(thread, dict) else thread),
        "messages": [message_detail_payload(message) for message in messages],
    }
