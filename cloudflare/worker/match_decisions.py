from __future__ import annotations


MATCH_DECISION_ACTIONS = {"approve": "approved", "reject": "rejected"}
APPROVAL_THREAD_MESSAGE = (
    "Thanks for reviewing my mini bid. I am ready to coordinate details here."
)


class MatchDecisionError(ValueError):
    pass


def parse_match_decision_path(path: str) -> tuple[int, str, str]:
    prefix = "/api/match-requests/"
    if not path.startswith(prefix):
        raise MatchDecisionError("Unsupported match decision route.")
    parts = [part for part in path[len(prefix) :].split("/") if part]
    if len(parts) != 2:
        raise MatchDecisionError("Unsupported match decision route.")
    request_id_raw, action = parts
    if not request_id_raw.isdigit() or int(request_id_raw) < 1:
        raise MatchDecisionError("Unsupported match decision route.")
    if action not in MATCH_DECISION_ACTIONS:
        raise MatchDecisionError("Unsupported match decision route.")
    return int(request_id_raw), action, MATCH_DECISION_ACTIONS[action]


def can_decide_match_request(user, match) -> bool:
    if not user or not match:
        return False
    if row_value(user, "status") != "active":
        return False
    if row_value(user, "role") == "admin":
        return True
    return row_value(user, "role") == "client" and row_value(user, "id") == row_value(match, "client_id")


def d1_change_count(result) -> int:
    if isinstance(result, dict):
        meta = result.get("meta") or result.get("result", {}).get("meta") or {}
    else:
        meta = getattr(result, "meta", {}) or {}
    try:
        return max(0, int(row_value(meta, "changes", 0) or 0))
    except (TypeError, ValueError):
        return 0


def match_decision_response(
    request_id: int,
    status: str,
    job_id: int | None = None,
    thread_id: int | None = None,
) -> dict:
    payload = {
        "ok": True,
        "request_id": request_id,
        "status": status,
    }
    if job_id:
        payload["job_id"] = job_id
    if thread_id:
        payload["thread_id"] = thread_id
        payload["url"] = f"/messages/{thread_id}"
    elif job_id:
        payload["url"] = f"/client/jobs/{job_id}"
    return payload


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)
