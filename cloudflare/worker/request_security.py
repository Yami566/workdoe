from __future__ import annotations

import secrets
from urllib.parse import urlsplit

SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
WORKDOE_REQUEST_HEADER = "X-Workdoe-Request"
WORKDOE_REQUEST_MARKER = "same-origin"
AUTH_API_PREFIX = "/api/auth/"
# Keep IDs exact across the browser and D1 binding's JavaScript number boundary.
MAX_URL_RECORD_ID = (1 << 53) - 1
MAX_URL_RECORD_ID_DIGITS = len(str(MAX_URL_RECORD_ID))


def parse_url_record_id(raw: str) -> int:
    if not 0 < len(raw) <= MAX_URL_RECORD_ID_DIGITS or not raw.isascii() or not raw.isdecimal():
        return 0
    record_id = int(raw)
    return record_id if 0 < record_id <= MAX_URL_RECORD_ID else 0


def requires_workdoe_request_marker(method: str, path: str) -> bool:
    return str(method or "").upper() not in SAFE_HTTP_METHODS and (
        path == "/logout" or str(path or "").startswith("/api/")
    )


def same_origin_api_write_allowed(method: str, path: str, marker: str) -> bool:
    if not requires_workdoe_request_marker(method, path):
        return True
    return secrets.compare_digest(str(marker or "").strip(), WORKDOE_REQUEST_MARKER)


def same_origin_form_write_allowed(
    request_url: str, *, origin: str, referer: str, fetch_site: str,
) -> bool:
    if fetch_site not in {"", "same-origin"}:
        return False
    try:
        target = urlsplit(request_url)
        if target.scheme not in {"https", "http"} or not target.netloc:
            return False
        if origin:
            # Origin is an exact serialized value, never a URL with a path or list.
            return origin == f"{target.scheme}://{target.netloc}"
        source = urlsplit(referer)
    except ValueError:
        return False
    return (source.scheme, source.netloc) == (target.scheme, target.netloc)


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
