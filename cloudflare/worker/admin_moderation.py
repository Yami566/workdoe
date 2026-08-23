from __future__ import annotations

import re


ADMIN_ACTION_RE = re.compile(
    r"^/api/admin/(?:(users)/([1-9][0-9]*)/(suspend|activate)"
    r"|(jobs)/([1-9][0-9]*)/(hide|restore)"
    r"|(photos)/(job)/([1-9][0-9]*)/(hide|restore)"
    r"|(photos)/(contractor)/([1-9][0-9]*)/(hide|restore)"
    r"|(messages)/([1-9][0-9]*)/(hide|restore)"
    r"|(reports)/([1-9][0-9]*)/(resolve)"
    r"|(credentials)/([1-9][0-9]*)/(verify|pending|reject|expire)"
    r"|(reviews)/([1-9][0-9]*)/(hide|restore)"
    r"|(review-reports)/([1-9][0-9]*)/(resolve))/?$"
)


class AdminModerationError(ValueError):
    pass


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def can_admin_moderate(user) -> bool:
    return bool(user) and row_value(user, "role") == "admin" and row_value(user, "status") == "active"


def parse_admin_moderation_path(path: str) -> dict:
    match = ADMIN_ACTION_RE.match(path or "")
    if not match:
        raise AdminModerationError("Unsupported admin moderation route.")
    groups = match.groups()
    if groups[0]:
        return {"target_type": "user", "target_id": int(groups[1]), "action": groups[2]}
    if groups[3]:
        return {"target_type": "job", "target_id": int(groups[4]), "action": groups[5]}
    if groups[6] and groups[7] == "job":
        return {"target_type": "job_photo", "target_id": int(groups[8]), "action": groups[9]}
    if groups[10] and groups[11] == "contractor":
        return {
            "target_type": "contractor_photo",
            "target_id": int(groups[12]),
            "action": groups[13],
        }
    if groups[14]:
        return {"target_type": "message", "target_id": int(groups[15]), "action": groups[16]}
    if groups[17]:
        return {"target_type": "report", "target_id": int(groups[18]), "action": groups[19]}
    if groups[20]:
        return {"target_type": "credential", "target_id": int(groups[21]), "action": groups[22]}
    if groups[23]:
        return {"target_type": "match_review", "target_id": int(groups[24]), "action": groups[25]}
    return {
        "target_type": "match_review_report",
        "target_id": int(groups[27]),
        "action": groups[28],
    }


def admin_target_query(target_type: str) -> str:
    queries = {
        "user": "SELECT 1 FROM users WHERE id = ? LIMIT 1",
        "job": "SELECT 1 FROM jobs WHERE id = ? LIMIT 1",
        "job_photo": "SELECT 1 FROM job_photos WHERE id = ? LIMIT 1",
        "contractor_photo": "SELECT 1 FROM contractor_photos WHERE id = ? LIMIT 1",
        "message": "SELECT 1 FROM messages WHERE id = ? LIMIT 1",
        "report": "SELECT 1 FROM reports WHERE id = ? LIMIT 1",
        "credential": "SELECT 1 FROM contractor_credentials WHERE id = ? LIMIT 1",
        "match_review": "SELECT 1 FROM match_reviews WHERE id = ? LIMIT 1",
        "match_review_report": "SELECT 1 FROM match_review_reports WHERE id = ? LIMIT 1",
    }
    try:
        return queries[target_type]
    except KeyError as exc:
        raise AdminModerationError("Unsupported admin moderation target.") from exc


def admin_update_statement(action: dict, now: str) -> tuple[str, list, str, str]:
    target_type = action["target_type"]
    target_id = action["target_id"]
    action_name = action["action"]
    if target_type == "user":
        status = "suspended" if action_name == "suspend" else "active"
        return (
            "UPDATE users SET status = ? WHERE id = ?",
            [status, target_id],
            f"Set user status to {status}.",
            status,
        )
    if target_type == "job":
        status = "hidden" if action_name == "hide" else "open"
        return (
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            [status, now, target_id],
            f"Set job status to {status}.",
            status,
        )
    if target_type == "job_photo":
        hidden = 1 if action_name == "hide" else 0
        return (
            "UPDATE job_photos SET is_hidden = ? WHERE id = ?",
            [hidden, target_id],
            f"Set job photo hidden={hidden}.",
            "hidden" if hidden else "visible",
        )
    if target_type == "contractor_photo":
        hidden = 1 if action_name == "hide" else 0
        return (
            "UPDATE contractor_photos SET is_hidden = ? WHERE id = ?",
            [hidden, target_id],
            f"Set contractor photo hidden={hidden}.",
            "hidden" if hidden else "visible",
        )
    if target_type == "message":
        hidden = 1 if action_name == "hide" else 0
        return (
            "UPDATE messages SET is_hidden = ? WHERE id = ?",
            [hidden, target_id],
            f"Set message hidden={hidden}.",
            "hidden" if hidden else "visible",
        )
    if target_type == "report":
        return (
            "UPDATE reports SET status = 'resolved', resolved_at = ? WHERE id = ?",
            [now, target_id],
            "Marked report resolved.",
            "resolved",
        )
    if target_type == "match_review":
        hidden = 1 if action_name == "hide" else 0
        return (
            "UPDATE match_reviews SET is_hidden = ?, updated_at = ? WHERE id = ?",
            [hidden, now, target_id],
            f"Set completed-work feedback hidden={hidden}.",
            "hidden" if hidden else "visible",
        )
    if target_type == "match_review_report":
        return (
            "UPDATE match_review_reports SET status = 'resolved', resolved_at = ? WHERE id = ?",
            [now, target_id],
            "Marked completed-work feedback report resolved.",
            "resolved",
        )
    raise AdminModerationError("Unsupported admin moderation target.")


def admin_moderation_response(action: dict, state: str) -> dict:
    return {
        "ok": True,
        "target_type": action["target_type"],
        "target_id": action["target_id"],
        "action": action["action"],
        "state": state,
        "url": "/admin",
    }
