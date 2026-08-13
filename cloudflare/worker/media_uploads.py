from __future__ import annotations

import re
import uuid


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_IMAGE_MIME = {
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MEDIA_UPLOAD_PATH_RE = re.compile(
    r"^/api/media/(?P<kind>jobs|contractors)/(?P<owner_id>[1-9][0-9]*)/upload/?$"
)


class MediaUploadError(ValueError):
    pass


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def media_upload_scope_from_path(path: str) -> tuple[str, int]:
    match = MEDIA_UPLOAD_PATH_RE.match(path or "")
    if not match:
        raise MediaUploadError("Unsupported media upload route.")
    scope = "job" if match.group("kind") == "jobs" else "contractor"
    return scope, int(match.group("owner_id"))


def normalize_upload_filename(original_filename: str) -> tuple[str, str]:
    filename = str(original_filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    cleaned = "".join(
        character if character.isalnum() or character in {" ", ".", "_", "-"} else "_"
        for character in filename
    ).strip(" .")
    if "." not in cleaned:
        raise MediaUploadError("Image file must have an allowed extension.")
    ext = cleaned.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise MediaUploadError("Unsupported image extension.")
    return cleaned[:160] or f"workdoe-upload.{ext}", ext


def safe_upload_metadata(original_filename: str, content_type: str, size_bytes: int | str) -> dict:
    filename, ext = normalize_upload_filename(original_filename)
    expected_type = ALLOWED_IMAGE_MIME[ext]
    actual_type = str(content_type or "").split(";", 1)[0].strip().lower()
    if actual_type != expected_type:
        raise MediaUploadError("Image MIME type does not match the allowed extension.")
    try:
        parsed_size = int(size_bytes)
    except (TypeError, ValueError) as exc:
        raise MediaUploadError("Image size is required.") from exc
    if parsed_size <= 0:
        raise MediaUploadError("Image file is empty.")
    if parsed_size > MAX_UPLOAD_BYTES:
        raise MediaUploadError("Image file is too large.")
    return {
        "original_filename": filename,
        "extension": ext,
        "content_type": expected_type,
        "size_bytes": parsed_size,
    }


def build_r2_upload_key(scope: str, owner_id: int, extension: str) -> str:
    if scope not in {"job", "contractor"}:
        raise MediaUploadError("Unsupported media upload scope.")
    owner = int(owner_id)
    if owner <= 0:
        raise MediaUploadError("Owner id must be positive.")
    prefix = "jobs" if scope == "job" else "contractors"
    return f"{prefix}/{owner}/{uuid.uuid4().hex}.{extension.lower()}"


def can_upload_job_photo(user, job) -> bool:
    if not user or row_value(user, "status") != "active":
        return False
    if row_value(user, "role") == "admin":
        return True
    return row_value(user, "role") == "client" and row_value(job, "client_id") == row_value(user, "id")


def can_upload_contractor_photo(user, contractor) -> bool:
    if not user or row_value(user, "status") != "active":
        return False
    return (
        row_value(user, "role") == "contractor"
        and row_value(contractor, "contractor_id") == row_value(user, "id")
    )


def upload_http_metadata(details: dict) -> dict:
    return {
        "contentType": details["content_type"],
        "contentDisposition": f'inline; filename="{details["original_filename"][:120]}"',
        "cacheControl": "private, no-store",
    }


def media_review_payload(
    scope: str,
    photo_id: int,
    owner_id: int,
    uploaded_by: int,
    stored_path: str,
    details: dict,
) -> dict:
    return {
        "type": "media-review",
        "scope": scope,
        "photo_id": int(photo_id),
        "owner_id": int(owner_id),
        "uploaded_by": int(uploaded_by),
        "stored_path": stored_path,
        "content_type": details["content_type"],
        "size_bytes": int(details["size_bytes"]),
        "checks": ["metadata", "moderation"],
    }


def validated_media_review_payload(body: dict) -> dict:
    if not isinstance(body, dict) or body.get("type") != "media-review":
        raise MediaUploadError("Unsupported media review payload.")
    scope = body.get("scope")
    if scope not in {"job", "contractor"}:
        raise MediaUploadError("Media review scope is invalid.")
    photo_id = int(body.get("photo_id") or 0)
    owner_id = int(body.get("owner_id") or 0)
    uploaded_by = int(body.get("uploaded_by") or 0)
    if min(photo_id, owner_id, uploaded_by) <= 0:
        raise MediaUploadError("Media review identifiers are invalid.")
    stored_path = str(body.get("stored_path") or "")
    expected_prefix = "jobs" if scope == "job" else "contractors"
    if not stored_path.startswith(f"{expected_prefix}/{owner_id}/"):
        raise MediaUploadError("Media review key does not match its owner.")
    details = safe_upload_metadata(
        f"review.{str(body.get('content_type', '')).rsplit('/', 1)[-1]}",
        body.get("content_type", ""),
        body.get("size_bytes", 0),
    )
    return {
        "type": "media-review",
        "scope": scope,
        "photo_id": photo_id,
        "owner_id": owner_id,
        "uploaded_by": uploaded_by,
        "stored_path": stored_path,
        "content_type": details["content_type"],
        "size_bytes": details["size_bytes"],
        "checks": list(body.get("checks") or []),
    }


def form_file_value(form_data, scope: str):
    names = (
        ("photo", "photos", "file")
        if scope == "job"
        else ("portfolio_photo", "portfolio_photos", "photo", "file")
    )
    getter = getattr(form_data, "get", None)
    if not callable(getter):
        raise MediaUploadError("Upload form data is not available.")
    for name in names:
        value = getter(name)
        if value:
            return value
    raise MediaUploadError("Image file is required.")


def uploaded_file_details(file) -> dict:
    return safe_upload_metadata(
        getattr(file, "name", "") or getattr(file, "filename", ""),
        getattr(file, "type", "") or getattr(file, "content_type", ""),
        getattr(file, "size", 0),
    )
