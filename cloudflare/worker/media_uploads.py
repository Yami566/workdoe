from __future__ import annotations

import re
import uuid

from media_access import MediaAccessError, safe_media_key
from request_security import parse_url_record_id

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_IMAGE_MIME = {
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
# Reject large source files before Cloudflare Images is invoked. The transformed
# object is held to a stricter storage limit below.
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_SANITIZED_IMAGE_BYTES = 1_500_000
MAX_JOB_PHOTOS_PER_PROJECT = 6
MAX_CONTRACTOR_PHOTOS_PER_PROFILE = 8
MAX_MEDIA_UPLOADS_PER_USER_PER_DAY = 12
IMAGE_SIGNATURE_BYTES = 12
SANITIZED_IMAGE_EXTENSION = "webp"
SANITIZED_IMAGE_MIME = "image/webp"
SANITIZED_IMAGE_MAX_DIMENSION = 1600
SANITIZED_IMAGE_QUALITY = 76
MEDIA_REVIEW_CHECKS = (
    "cloudflare-images-decode",
    "metadata-stripped",
    "animation-flattened",
    "moderation",
)
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
    record_id = parse_url_record_id(match.group("owner_id")) if match else 0
    if not record_id:
        raise MediaUploadError("Unsupported media upload route.")
    scope = "job" if match.group("kind") == "jobs" else "contractor"
    return scope, record_id


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


def generic_media_filename(extension: str = SANITIZED_IMAGE_EXTENSION) -> str:
    """Return the only filename Workdoe retains or presents for uploaded media.

    A user-controlled filename may contain an address, a name, or other private
    information. It is useful only for extension validation, so discard it
    before the metadata reaches D1, R2, an audit screen, or a browser.
    """
    normalized = str(extension or "").strip().lower().lstrip(".")
    if normalized not in ALLOWED_IMAGE_EXTENSIONS:
        normalized = SANITIZED_IMAGE_EXTENSION
    return f"workdoe-photo.{normalized}"


def safe_upload_metadata(
    original_filename: str,
    content_type: str,
    size_bytes: int | str,
    maximum_bytes: int = MAX_UPLOAD_BYTES,
) -> dict:
    _, ext = normalize_upload_filename(original_filename)
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
    if parsed_size > maximum_bytes:
        raise MediaUploadError("Image file is too large.")
    return {
        "original_filename": generic_media_filename(ext),
        "extension": ext,
        "content_type": expected_type,
        "size_bytes": parsed_size,
    }


def image_signature_matches(extension: str, prefix: bytes) -> bool:
    ext = str(extension or "").lower()
    value = bytes(prefix or b"")
    if ext == "png":
        return value.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in {"jpg", "jpeg"}:
        return value.startswith(b"\xff\xd8\xff")
    if ext == "gif":
        return value.startswith((b"GIF87a", b"GIF89a"))
    if ext == "webp":
        return len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WEBP"
    return False


async def validate_uploaded_file_signature(file, extension: str) -> None:
    try:
        from js import Uint8Array

        prefix_blob = file.slice(0, IMAGE_SIGNATURE_BYTES)
        prefix_buffer = await prefix_blob.arrayBuffer()
        prefix = bytes(Uint8Array.new(prefix_buffer).to_py())
    except Exception as exc:
        raise MediaUploadError("Image content could not be inspected.") from exc
    if not image_signature_matches(extension, prefix):
        raise MediaUploadError("Image content does not match its file type.")


async def sanitize_uploaded_image(images_binding, file, js_object) -> dict:
    if not images_binding or not callable(getattr(images_binding, "info", None)):
        raise TypeError("Cloudflare Images binding is unavailable.")
    if not callable(getattr(images_binding, "input", None)):
        raise TypeError("Cloudflare Images binding is unavailable.")

    try:
        source_info = await images_binding.info(file.stream())
        source_width = int(row_value(source_info, "width", 0) or 0)
        source_height = int(row_value(source_info, "height", 0) or 0)
    except Exception as exc:
        raise MediaUploadError("Image could not be decoded.") from exc
    if source_width <= 0 or source_height <= 0:
        raise MediaUploadError("Image dimensions are invalid.")

    try:
        transformer = images_binding.input(file.stream()).transform(
            js_object(
                {
                    "width": SANITIZED_IMAGE_MAX_DIMENSION,
                    "height": SANITIZED_IMAGE_MAX_DIMENSION,
                    "fit": "scale-down",
                    "metadata": "none",
                }
            )
        )
        result = await transformer.output(
            js_object(
                {
                    "format": SANITIZED_IMAGE_MIME,
                    "quality": SANITIZED_IMAGE_QUALITY,
                    "anim": False,
                }
            )
        )
        response = result.response()
        if not bool(getattr(response, "ok", False)):
            raise RuntimeError("Cloudflare Images rejected the transform.")
        body = await response.arrayBuffer()
        size_bytes = int(getattr(body, "byteLength", 0) or 0)
    except MediaUploadError:
        raise
    except Exception as exc:
        raise RuntimeError("Cloudflare Images could not sanitize the upload.") from exc
    if size_bytes <= 0 or size_bytes > MAX_SANITIZED_IMAGE_BYTES:
        raise RuntimeError("Sanitized image size is invalid.")
    return {
        "body": body,
        "content_type": SANITIZED_IMAGE_MIME,
        "extension": SANITIZED_IMAGE_EXTENSION,
        "size_bytes": size_bytes,
        "source_width": source_width,
        "source_height": source_height,
    }


def sanitized_upload_details(source_details: dict, sanitized: dict) -> dict:
    return {
        **source_details,
        "original_filename": generic_media_filename(SANITIZED_IMAGE_EXTENSION),
        "extension": SANITIZED_IMAGE_EXTENSION,
        "content_type": SANITIZED_IMAGE_MIME,
        "size_bytes": int(sanitized["size_bytes"]),
        "source_width": int(sanitized["source_width"]),
        "source_height": int(sanitized["source_height"]),
        "sanitization": "cloudflare-images-webp",
    }


def media_upload_quota_error(
    scope: str,
    resource_count: int,
    recent_upload_count: int,
) -> str | None:
    """Return a stable user-facing quota error before image processing begins."""
    if scope == "job" and resource_count >= MAX_JOB_PHOTOS_PER_PROJECT:
        return "This project already has the maximum of 6 photos."
    if scope == "contractor" and resource_count >= MAX_CONTRACTOR_PHOTOS_PER_PROFILE:
        return "Your contractor profile already has the maximum of 8 photos."
    if recent_upload_count >= MAX_MEDIA_UPLOADS_PER_USER_PER_DAY:
        return "You have reached the daily upload limit. Try again tomorrow."
    return None


def build_r2_upload_key(scope: str, owner_id: int, extension: str) -> str:
    if scope not in {"job", "contractor"}:
        raise MediaUploadError("Unsupported media upload scope.")
    owner = int(owner_id)
    if owner <= 0:
        raise MediaUploadError("Owner id must be positive.")
    prefix = "jobs" if scope == "job" else "contractors"
    return f"{prefix}/{owner}/{uuid.uuid4().hex}.{extension.lower()}"


def media_metadata_delete_statement(
    scope: str,
    photo_id: int,
    owner_id: int,
    stored_path: str,
) -> tuple[str, tuple[int, int, str]]:
    photo = int(photo_id)
    owner = int(owner_id)
    key = str(stored_path or "").strip()
    if scope not in {"job", "contractor"} or min(photo, owner) <= 0 or not key:
        raise MediaUploadError("Media cleanup identifiers are invalid.")
    if scope == "job":
        return (
            "DELETE FROM job_photos WHERE id = ? AND job_id = ? AND stored_path = ?",
            (photo, owner, key),
        )
    return (
        "DELETE FROM contractor_photos WHERE id = ? AND contractor_id = ? AND stored_path = ?",
        (photo, owner, key),
    )


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
        "contentDisposition": f'inline; filename="workdoe-upload.{details["extension"]}"',
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
        "checks": list(MEDIA_REVIEW_CHECKS),
    }


def validated_media_review_payload(body: dict) -> dict:
    if not isinstance(body, dict) or body.get("type") != "media-review":
        raise MediaUploadError("Unsupported media review payload.")
    scope = body.get("scope")
    if scope not in ("job", "contractor"):
        raise MediaUploadError("Media review scope is invalid.")
    photo_id, owner_id, uploaded_by = (body.get(key) for key in ("photo_id", "owner_id", "uploaded_by"))
    if any(type(value) is not int or not 0 < value < 2**53 for value in (photo_id, owner_id, uploaded_by)):
        raise MediaUploadError("Media review identifiers are invalid.")
    stored_path = body.get("stored_path")
    expected_prefix = "jobs" if scope == "job" else "contractors"
    try:
        if not isinstance(stored_path, str) or safe_media_key(stored_path, f"{expected_prefix}/{owner_id}") != stored_path:
            raise MediaUploadError("Media review key is invalid.")
    except MediaAccessError as exc:
        raise MediaUploadError("Media review key is invalid.") from exc
    content_type = body.get("content_type")
    if content_type not in ALLOWED_IMAGE_MIME.values():
        raise MediaUploadError("Media review content type is invalid.")
    size_bytes = body.get("size_bytes")
    if type(size_bytes) is not int or not 0 < size_bytes <= MAX_SANITIZED_IMAGE_BYTES:
        raise MediaUploadError("Media review size is invalid.")
    checks = body.get("checks", [])
    if not isinstance(checks, list) or len(checks) > len(MEDIA_REVIEW_CHECKS) or any(
        check not in MEDIA_REVIEW_CHECKS for check in checks
    ):
        raise MediaUploadError("Media review checks are invalid.")
    return {
        "type": "media-review",
        "scope": scope,
        "photo_id": photo_id,
        "owner_id": owner_id,
        "uploaded_by": uploaded_by,
        "stored_path": stored_path,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "checks": checks,
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
