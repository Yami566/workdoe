from __future__ import annotations

from datetime import datetime, timezone


ACTIVATION_NOT_OPEN_MESSAGE = (
    "This service is not open in that area yet. Choose another service or location."
)
ACTIVATION_STATUSES = {"candidate", "active", "paused", "retired"}
PILOT_SERVICE_SLUGS = (
    "house-cleaning",
    "deep-cleaning",
    "move-cleaning",
    "packing-unpacking",
    "heavy-lifting",
    "furniture-assembly",
)
PILOT_ZONE_SLUGS = (
    "district-of-columbia",
    "arlington-county-va",
    "alexandria-va",
)
PILOT_ALLOWED_SCOPE = (
    "Interior cleaning, packing or unpacking, in-home lifting, and freestanding "
    "furniture assembly within the selected service definition."
)
PILOT_EXCLUDED_SCOPE = (
    "No vehicle transport, disposal, wall attachment, exterior access, utility "
    "connection, structural work, or alteration of real property."
)
PILOT_REQUIREMENTS = (
    "Operator review of local business requirements, insurance, worker safety, "
    "building access, and service-specific exclusions is required before activation."
)


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return getattr(row, key, default)


def enabled_flag(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _utc_datetime(value=None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        raw = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def activation_is_live(row, now=None) -> bool:
    if not row or row_value(row, "status") != "active":
        return False
    for field in ("allowed_scope", "excluded_scope", "requirements_summary"):
        if not str(row_value(row, field, "") or "").strip():
            return False
    if not row_value(row, "approved_at") or not row_value(row, "reviewed_at"):
        return False
    expires_at = row_value(row, "expires_at")
    if expires_at and _utc_datetime(expires_at) <= _utc_datetime(now):
        return False
    try:
        minimum = max(1, int(row_value(row, "minimum_eligible_contractors", 3) or 3))
        eligible = max(0, int(row_value(row, "eligible_contractors", 0) or 0))
    except (TypeError, ValueError):
        return False
    return eligible >= minimum
