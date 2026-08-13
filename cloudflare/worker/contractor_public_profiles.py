from __future__ import annotations

import re


CONTRACTOR_PROFILE_PATH_RE = re.compile(r"^/api/contractors/([1-9][0-9]*)/?$")
PUBLIC_CONTRACTOR_CONTACT_POLICY = (
    "Clients approve a contractor's mini bid before a private Workdoe message thread opens."
)


class ContractorPublicProfileError(ValueError):
    pass


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def parse_public_contractor_id(path: str) -> int:
    match = CONTRACTOR_PROFILE_PATH_RE.match(path or "")
    if not match:
        raise ContractorPublicProfileError("Unsupported contractor profile route.")
    return int(match.group(1))


def is_active_admin(user) -> bool:
    return bool(user) and row_value(user, "role") == "admin" and row_value(user, "status") == "active"


def can_view_public_contractor_profile(user, contractor) -> bool:
    if not contractor:
        return False
    if row_value(contractor, "status") == "active":
        return True
    return is_active_admin(user)


def public_contractor_name(contractor) -> str:
    return (
        row_value(contractor, "business_name")
        or row_value(contractor, "company_name")
        or row_value(contractor, "display_name")
        or "Workdoe contractor"
    )


def contractor_public_photo_payload(photo) -> dict:
    return {
        "id": row_value(photo, "id"),
        "url": f"/media/contractors/{row_value(photo, 'id')}",
        "original_filename": row_value(photo, "original_filename", "") or "",
        "created_at": row_value(photo, "created_at", "") or "",
    }


def public_contractor_profile_payload(contractor, photos: list, viewer) -> dict:
    contractor_id = row_value(contractor, "id") or row_value(contractor, "user_id")
    profile = {
        "id": contractor_id,
        "business_name": public_contractor_name(contractor),
        "trades": row_value(contractor, "trades", "") or "",
        "service_area": row_value(contractor, "service_area", "") or "DMV area",
        "intro": row_value(contractor, "intro", "") or "This contractor is still completing their profile.",
        "insurance_status": row_value(contractor, "insurance_status", "") or "Available on request",
        "license_number": row_value(contractor, "license_number", "") or "Not listed",
        "years_in_business": row_value(contractor, "years_in_business"),
        "updated_at": row_value(contractor, "updated_at", "") or "",
        "url": f"/contractors/{contractor_id}",
        "contact_policy": PUBLIC_CONTRACTOR_CONTACT_POLICY,
        "photos": [contractor_public_photo_payload(photo) for photo in photos],
    }
    if is_active_admin(viewer):
        profile["status"] = row_value(contractor, "status", "") or ""
    return {"ok": True, "contractor": profile}
