from __future__ import annotations

import re

PRIVATE_MEDIA_NOTICE = (
    "Private Workdoe media is served only after role, ownership, match, "
    "and moderation checks."
)

MEDIA_PATH_RE = re.compile(r"^/media/(?P<kind>jobs|contractors)/(?P<photo_id>[1-9][0-9]*)/?$")


class MediaAccessError(ValueError):
    pass


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def media_scope_from_path(path: str) -> tuple[str, int]:
    match = MEDIA_PATH_RE.match(path or "")
    if not match:
        raise MediaAccessError("Unsupported media route.")
    scope = "job" if match.group("kind") == "jobs" else "contractor"
    return scope, int(match.group("photo_id"))


def safe_media_key(stored_path: str, expected_prefix: str) -> str:
    value = str(stored_path or "").strip()
    prefix = str(expected_prefix or "").strip().strip("/")
    if not value or not prefix:
        raise MediaAccessError("Media key is missing.")
    if value.startswith("/") or "\\" in value or "//" in value:
        raise MediaAccessError("Media key is not a private scoped key.")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise MediaAccessError("Media key contains an unsafe path segment.")
    if not value.startswith(f"{prefix}/"):
        raise MediaAccessError("Media key does not match its database owner.")
    return value


def is_admin(user) -> bool:
    return row_value(user, "role") == "admin"


def is_active_user(user) -> bool:
    return bool(user) and row_value(user, "status", "active") == "active"


def truthy(value) -> bool:
    return value in (True, 1, "1", "true", "True", "yes", "on")


def can_view_job_photo(user, photo) -> bool:
    if not is_active_user(user):
        return False
    if is_admin(user):
        return True
    if truthy(row_value(photo, "is_hidden")):
        return False
    user_id = row_value(user, "id")
    role = row_value(user, "role")
    if role == "client" and row_value(photo, "client_id") == user_id:
        return True
    if role != "contractor":
        return False
    if row_value(photo, "client_status") != "active":
        return False
    if row_value(photo, "status") == "open":
        return True
    return truthy(row_value(photo, "has_approved_match"))


def can_view_contractor_photo(user, photo) -> bool:
    owner_or_admin = bool(user) and (
        is_admin(user) or row_value(photo, "contractor_id") == row_value(user, "id")
    )
    if owner_or_admin and is_active_user(user):
        return True
    if truthy(row_value(photo, "is_hidden")):
        return False
    return row_value(photo, "status") == "active"


def inline_content_disposition(original_filename: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {" ", ".", "_", "-"} else "_"
        for character in str(original_filename or "").strip()
    ).strip()
    filename = cleaned or "workdoe-media"
    return f'inline; filename="{filename[:120]}"'
