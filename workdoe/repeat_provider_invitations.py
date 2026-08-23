from __future__ import annotations

import re


INVITATION_STATUSES = {"pending", "bid_sent", "declined", "withdrawn"}
INVITATION_STATUS_LABELS = {
    "pending": "Waiting for contractor",
    "bid_sent": "New mini bid sent",
    "declined": "Contractor passed",
    "withdrawn": "Invitation withdrawn",
}
INVITATION_ACTION_RE = re.compile(
    r"^/api/repeat-invitations/([1-9][0-9]*)/(decline|withdraw)$"
)


class RepeatProviderInvitationError(ValueError):
    def __init__(self, message: str, status: int = 400):
        self.status = status
        super().__init__(message)


def row_value(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, default)


def positive_int(value) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def validate_repeat_invitation_source(user, source) -> dict:
    if not user:
        raise RepeatProviderInvitationError("Sign in required.", 401)
    if row_value(user, "status") != "active" or row_value(user, "role") != "client":
        raise RepeatProviderInvitationError(
            "Only an active consumer can invite a prior contractor.", 403
        )
    if not source:
        raise RepeatProviderInvitationError("Completed match not found.", 404)

    client_id = positive_int(row_value(source, "client_id"))
    if client_id != positive_int(row_value(user, "id")):
        raise RepeatProviderInvitationError("Completed match not found.", 404)
    if row_value(source, "source_job_status") != "closed":
        raise RepeatProviderInvitationError(
            "Only a closed project can invite its prior contractor.", 409
        )
    if row_value(source, "close_reason") != "workdoe-match":
        raise RepeatProviderInvitationError(
            "This project was not closed as a Workdoe match.", 409
        )
    if row_value(source, "match_status") != "approved" or not row_value(
        source, "verified_at"
    ):
        raise RepeatProviderInvitationError(
            "Both participants must confirm the prior Workdoe project first.", 409
        )
    if row_value(source, "contractor_status") != "active":
        raise RepeatProviderInvitationError(
            "That contractor is not currently available for an invitation.", 409
        )

    source_job_id = positive_int(row_value(source, "source_job_id"))
    source_match_request_id = positive_int(
        row_value(source, "source_match_request_id")
    )
    contractor_id = positive_int(row_value(source, "contractor_id"))
    service_slug = str(row_value(source, "service_slug", "") or "").strip()
    if not source_job_id or not source_match_request_id or not contractor_id or not service_slug:
        raise RepeatProviderInvitationError(
            "The completed match is missing reusable service information.", 409
        )
    return {
        "source_job_id": source_job_id,
        "source_match_request_id": source_match_request_id,
        "client_id": client_id,
        "contractor_id": contractor_id,
        "contractor_name": str(
            row_value(source, "contractor_name", "Contractor") or "Contractor"
        ),
        "service_slug": service_slug,
        "category": str(row_value(source, "category", "Other") or "Other"),
    }


def validate_repeat_invitation_service(source: dict, service_slug: str) -> None:
    if str(service_slug or "").strip() != str(source.get("service_slug") or ""):
        raise RepeatProviderInvitationError(
            "A repeat invitation must keep the same service as the completed project."
        )


def repeat_invitation_new_job_url(source_job_id: int, match_request_id: int) -> str:
    return (
        f"/jobs/new?repeat={positive_int(source_job_id)}"
        f"&invite={positive_int(match_request_id)}"
    )


def repeat_invitation_response(row) -> dict:
    invitation_id = positive_int(row_value(row, "id"))
    job_id = positive_int(row_value(row, "job_id"))
    status = str(row_value(row, "status", "pending") or "pending")
    if status not in INVITATION_STATUSES:
        status = "pending"
    return {
        "id": invitation_id,
        "job_id": job_id,
        "source_job_id": positive_int(row_value(row, "source_job_id")),
        "source_match_request_id": positive_int(
            row_value(row, "source_match_request_id")
        ),
        "client_id": positive_int(row_value(row, "client_id")),
        "contractor_id": positive_int(row_value(row, "contractor_id")),
        "contractor_name": str(
            row_value(row, "contractor_name", "Contractor") or "Contractor"
        ),
        "project_title": str(row_value(row, "project_title", "") or ""),
        "category": str(row_value(row, "category", "") or ""),
        "service_slug": str(row_value(row, "service_slug", "") or ""),
        "city": str(row_value(row, "city", "") or ""),
        "state": str(row_value(row, "state", "") or ""),
        "desired_date": str(row_value(row, "desired_date", "") or ""),
        "job_status": str(row_value(row, "job_status", "") or ""),
        "status": status,
        "status_label": INVITATION_STATUS_LABELS[status],
        "created_at": str(row_value(row, "created_at", "") or ""),
        "responded_at": str(row_value(row, "responded_at", "") or ""),
        "detail_url": f"/jobs/{job_id}",
        "client_detail_url": f"/client/jobs/{job_id}",
        "decline_url": f"/api/repeat-invitations/{invitation_id}/decline",
        "withdraw_url": f"/api/repeat-invitations/{invitation_id}/withdraw",
    }


def validate_invitation_action(user, invitation, action: str) -> None:
    if action not in {"decline", "withdraw"}:
        raise RepeatProviderInvitationError("Unsupported invitation action.", 404)
    if not user:
        raise RepeatProviderInvitationError("Sign in required.", 401)
    if row_value(user, "status") != "active":
        raise RepeatProviderInvitationError("This account is not active.", 403)
    expected_role = "contractor" if action == "decline" else "client"
    expected_id = row_value(invitation, f"{expected_role}_id")
    if row_value(user, "role") != expected_role or positive_int(
        row_value(user, "id")
    ) != positive_int(expected_id):
        raise RepeatProviderInvitationError("Invitation not found.", 404)
    if row_value(invitation, "status") != "pending":
        raise RepeatProviderInvitationError(
            "This invitation has already been answered.", 409
        )


def parse_invitation_action_path(path: str) -> tuple[int, str]:
    match = INVITATION_ACTION_RE.fullmatch(path or "")
    if not match:
        raise RepeatProviderInvitationError("Unsupported invitation route.", 404)
    return int(match.group(1)), match.group(2)
