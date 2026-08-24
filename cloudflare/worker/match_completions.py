from __future__ import annotations


class MatchCompletionError(ValueError):
    def __init__(self, message: str, status: int = 400):
        self.status = status
        super().__init__(message)


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def completion_state(completion) -> str:
    if row_value(completion, "verified_at"):
        return "verified"
    client_confirmed = bool(row_value(completion, "client_confirmed_at"))
    contractor_confirmed = bool(row_value(completion, "contractor_confirmed_at"))
    if client_confirmed:
        return "client_confirmed"
    if contractor_confirmed:
        return "contractor_confirmed"
    return "awaiting"


def completion_label(completion, viewer_role: str = "") -> str:
    state = completion_state(completion)
    if state == "verified":
        return "Verified complete"
    if state == "client_confirmed":
        return (
            "You confirmed - waiting for contractor"
            if viewer_role == "client"
            else "Consumer confirmed - confirm completion"
        )
    if state == "contractor_confirmed":
        return (
            "Contractor confirmed - confirm completion"
            if viewer_role == "client"
            else "You confirmed - waiting for consumer"
        )
    return "Awaiting both confirmations"


def participant_role(user, match) -> str:
    if not user or row_value(user, "status") != "active":
        return ""
    user_id = int(row_value(user, "id", 0) or 0)
    if row_value(user, "role") == "client" and user_id == int(
        row_value(match, "client_id", 0) or 0
    ):
        return "client"
    if row_value(user, "role") == "contractor" and user_id == int(
        row_value(match, "contractor_id", 0) or 0
    ):
        return "contractor"
    return ""


def validate_completion_confirmation(user, match) -> str:
    if not match:
        raise MatchCompletionError("Approved match not found.", 404)
    role = participant_role(user, match)
    if not role:
        raise MatchCompletionError("Only match participants can confirm completion.", 403)
    if row_value(match, "match_status", row_value(match, "status")) != "approved":
        raise MatchCompletionError("Only an approved match can be completed.", 409)
    if row_value(match, "job_status") != "closed":
        raise MatchCompletionError("Close the project before confirming completion.", 409)
    if row_value(match, "close_reason") != "workdoe-match":
        raise MatchCompletionError(
            "Completion can be confirmed only for work matched through Workdoe.",
            409,
        )
    return role


def can_confirm_completion(user, match) -> bool:
    try:
        role = validate_completion_confirmation(user, match)
    except MatchCompletionError:
        return False
    confirmation_key = f"{role}_confirmed_at"
    return not bool(row_value(match, confirmation_key))


def completion_response(completion) -> dict:
    state = completion_state(completion)
    return {
        "match_request_id": int(row_value(completion, "match_request_id", 0) or 0),
        "state": state,
        "client_confirmed": bool(row_value(completion, "client_confirmed_at")),
        "contractor_confirmed": bool(row_value(completion, "contractor_confirmed_at")),
        "verified": state == "verified",
        "verified_at": str(row_value(completion, "verified_at", "") or ""),
    }


def parse_match_completion_path(path: str) -> int:
    prefix = "/api/match-requests/"
    suffix = "/complete"
    if not path.startswith(prefix) or not path.endswith(suffix):
        raise MatchCompletionError("Completion route is invalid.", 404)
    raw = path[len(prefix) : -len(suffix)].strip("/")
    if not raw.isdigit() or int(raw) <= 0:
        raise MatchCompletionError("Completion route is invalid.", 404)
    return int(raw)
