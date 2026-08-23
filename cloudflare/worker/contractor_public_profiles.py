from __future__ import annotations

import re

from contractor_credentials import public_credential_responses
from contractor_preferences import availability_response
from contractor_profiles import normalized_profile_website, profile_website_label
from contractor_reputation import contractor_reputation
from market_fit import (
    ZONE_BY_SLUG,
    infer_service_slugs_from_trades,
    infer_zone_slugs_from_area,
    normalize_service_slugs,
    normalize_zone_slugs,
)
from service_taxonomy import SERVICE_BY_SLUG

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


def can_view_contractor_website(
    viewer,
    contractor_id: int,
    has_bid_relationship: bool = False,
) -> bool:
    if not viewer or row_value(viewer, "status") != "active":
        return False
    if is_active_admin(viewer):
        return True
    if row_value(viewer, "role") == "contractor":
        return row_value(viewer, "id") == contractor_id
    return row_value(viewer, "role") == "client" and has_bid_relationship


def contractor_choice_context(viewer, contractor_id: int, relationship) -> dict | None:
    if (
        not viewer
        or row_value(viewer, "role") != "client"
        or row_value(viewer, "status") != "active"
        or not relationship
    ):
        return None
    try:
        viewer_id = int(row_value(viewer, "id", 0) or 0)
        client_id = int(row_value(relationship, "client_id", 0) or 0)
        related_contractor_id = int(
            row_value(relationship, "contractor_id", 0) or 0
        )
        job_id = int(row_value(relationship, "job_id", 0) or 0)
        request_id = int(row_value(relationship, "request_id", 0) or 0)
        thread_id = int(row_value(relationship, "thread_id", 0) or 0)
    except (TypeError, ValueError):
        return None
    if (
        viewer_id < 1
        or viewer_id != client_id
        or related_contractor_id != contractor_id
        or job_id < 1
        or request_id < 1
    ):
        return None
    status = str(row_value(relationship, "status", "") or "")
    return {
        "job_id": job_id,
        "job_title": str(
            row_value(relationship, "job_title", "Project") or "Project"
        ),
        "request_id": request_id,
        "status": status,
        "back_url": f"/client/jobs/{job_id}#mini-bids",
        "can_choose": status == "pending",
        "thread_url": f"/messages/{thread_id}" if status == "approved" and thread_id else "",
    }


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
        "created_at": row_value(photo, "created_at", "") or "",
    }


def public_contractor_profile_payload(
    contractor,
    photos: list,
    viewer,
    market_fit: dict | None = None,
    website_visible: bool = False,
    credentials: list | None = None,
    availability=None,
) -> dict:
    contractor_id = row_value(contractor, "id") or row_value(contractor, "user_id")
    selections = market_fit or {}
    service_slugs = normalize_service_slugs(selections.get("service_slugs"))
    zone_slugs = normalize_zone_slugs(selections.get("service_zone_slugs"))
    if not service_slugs:
        service_slugs = infer_service_slugs_from_trades(row_value(contractor, "trades", ""))
    if not zone_slugs:
        zone_slugs = infer_zone_slugs_from_area(row_value(contractor, "service_area", ""))
    public_credentials = public_credential_responses(credentials or [])
    reputation = contractor_reputation(
        row_value(contractor, "verified_completions", 0),
        len(public_credentials),
        sum(
            1
            for credential in public_credentials
            if credential.get("credential_type") == "trade_license"
        ),
    )
    profile = {
        "id": contractor_id,
        "business_name": public_contractor_name(contractor),
        "trades": row_value(contractor, "trades", "") or "",
        "service_area": row_value(contractor, "service_area", "") or "DMV area",
        "intro": row_value(contractor, "intro", "") or "This contractor is still completing their profile.",
        "insurance_status": row_value(contractor, "insurance_status", "") or "Available on request",
        "license_number": row_value(contractor, "license_number", "") or "Not listed",
        "years_in_business": row_value(contractor, "years_in_business"),
        "verified_completions": int(
            row_value(contractor, "verified_completions", 0) or 0
        ),
        "updated_at": row_value(contractor, "updated_at", "") or "",
        "url": f"/contractors/{contractor_id}",
        "contact_policy": PUBLIC_CONTRACTOR_CONTACT_POLICY,
        "photos": [contractor_public_photo_payload(photo) for photo in photos],
        "services": [SERVICE_BY_SLUG[slug] for slug in service_slugs],
        "service_zones": [ZONE_BY_SLUG[slug] for slug in zone_slugs],
        "credentials": public_credentials,
        "reputation": reputation,
        "availability": availability_response(availability),
    }
    if is_active_admin(viewer):
        profile["status"] = row_value(contractor, "status", "") or ""
    if website_visible:
        website = normalized_profile_website(row_value(contractor, "website", ""))
        if website:
            profile["website"] = website
            profile["website_label"] = profile_website_label(website)
    return {"ok": True, "contractor": profile}
