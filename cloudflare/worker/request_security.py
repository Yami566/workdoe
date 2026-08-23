from __future__ import annotations

import secrets


SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
WORKDOE_REQUEST_HEADER = "X-Workdoe-Request"
WORKDOE_REQUEST_MARKER = "same-origin"
AUTH_API_PREFIX = "/api/auth/"


def requires_workdoe_request_marker(method: str, path: str) -> bool:
    return str(method or "").upper() not in SAFE_HTTP_METHODS and str(path or "").startswith(
        "/api/"
    )


def same_origin_api_write_allowed(method: str, path: str, marker: str) -> bool:
    if not requires_workdoe_request_marker(method, path):
        return True
    return secrets.compare_digest(str(marker or "").strip(), WORKDOE_REQUEST_MARKER)


def authenticated_write_rate_limit_required(method: str, path: str) -> bool:
    normalized_path = str(path or "")
    return (
        str(method or "").upper() == "POST"
        and normalized_path.startswith("/api/")
        and not normalized_path.startswith(AUTH_API_PREFIX)
    )


def authenticated_write_rate_limit_key(user_id: int) -> str:
    normalized_user_id = int(user_id)
    if normalized_user_id <= 0:
        raise ValueError("Rate-limit user ID must be positive.")
    return f"workdoe-user:{normalized_user_id}"
