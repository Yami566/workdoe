from __future__ import annotations

import ipaddress
import re
from datetime import date, datetime, timezone
from urllib.parse import urlparse, urlunparse

CREDENTIAL_TYPES = (
    ("trade_license", "Trade license"),
    ("business_registration", "Business registration"),
    ("insurance", "Insurance certificate"),
)
CREDENTIAL_TYPE_LABELS = dict(CREDENTIAL_TYPES)
CREDENTIAL_JURISDICTIONS = (
    ("DC", "District of Columbia"),
    ("MD", "Maryland"),
    ("VA", "Virginia"),
    ("FEDERAL", "Federal"),
    ("OTHER", "Other"),
)
CREDENTIAL_JURISDICTION_LABELS = dict(CREDENTIAL_JURISDICTIONS)
CREDENTIAL_STATUSES = {
    "self_reported",
    "pending",
    "verified",
    "expired",
    "rejected",
}
CREDENTIAL_STATUS_LABELS = {
    "self_reported": "Awaiting review",
    "pending": "More information needed",
    "verified": "Source checked",
    "expired": "Expired",
    "rejected": "Not confirmed",
}
CREDENTIAL_REVIEW_ACTIONS = {
    "verify": "verified",
    "pending": "pending",
    "reject": "rejected",
    "expire": "expired",
}
CREDENTIAL_IDENTIFIER_MIN_LENGTH = 3
CREDENTIAL_IDENTIFIER_MAX_LENGTH = 80
CREDENTIAL_NAME_MAX_LENGTH = 120
CREDENTIAL_SOURCE_MAX_LENGTH = 300
CREDENTIAL_REVIEW_NOTE_MAX_LENGTH = 500
CREDENTIAL_HOST_LABEL_RE = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)


class ContractorCredentialError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def normalized_credential_source_url(value: str | None) -> str:
    raw_value = (value or "").strip()
    if not raw_value or len(raw_value) > CREDENTIAL_SOURCE_MAX_LENGTH:
        return ""
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in raw_value
    ):
        return ""
    try:
        parsed = urlparse(raw_value)
        port = parsed.port
        hostname = (parsed.hostname or "").rstrip(".")
        ascii_hostname = hostname.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        return ""
    if (
        parsed.scheme.lower() != "https"
        or not ascii_hostname
        or parsed.username
        or parsed.password
        or port not in {None, 443}
        or ascii_hostname == "localhost"
        or "." not in ascii_hostname
        or any(
            not CREDENTIAL_HOST_LABEL_RE.fullmatch(label)
            for label in ascii_hostname.split(".")
        )
    ):
        return ""
    try:
        ipaddress.ip_address(ascii_hostname)
    except ValueError:
        pass
    else:
        return ""
    return urlunparse(
        (
            "https",
            ascii_hostname,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def normalized_optional_date(value: str | None) -> str:
    raw_value = (value or "").strip()
    if not raw_value:
        return ""
    try:
        return date.fromisoformat(raw_value).isoformat()
    except ValueError:
        return ""


def contractor_credential_claim_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ContractorCredentialError(["Credential claim must be an object."])
    claim = {
        "credential_type": compact_spaces(payload.get("credential_type")),
        "jurisdiction": compact_spaces(payload.get("jurisdiction")).upper(),
        "claimed_identifier": compact_spaces(payload.get("claimed_identifier")),
        "claimed_name": compact_spaces(payload.get("claimed_name")),
        "source_url": normalized_credential_source_url(payload.get("source_url")),
        "expires_at": normalized_optional_date(payload.get("expires_at")),
    }
    errors: list[str] = []
    if claim["credential_type"] not in CREDENTIAL_TYPE_LABELS:
        errors.append("Choose a credential type.")
    if claim["jurisdiction"] not in CREDENTIAL_JURISDICTION_LABELS:
        errors.append("Choose a credential jurisdiction.")
    identifier_length = len(claim["claimed_identifier"])
    if identifier_length < CREDENTIAL_IDENTIFIER_MIN_LENGTH:
        errors.append("Add the credential number or record identifier.")
    elif identifier_length > CREDENTIAL_IDENTIFIER_MAX_LENGTH:
        errors.append(
            f"Keep the credential identifier under {CREDENTIAL_IDENTIFIER_MAX_LENGTH} characters."
        )
    if len(claim["claimed_name"]) > CREDENTIAL_NAME_MAX_LENGTH:
        errors.append(
            f"Keep the name on the record under {CREDENTIAL_NAME_MAX_LENGTH} characters."
        )
    raw_source = (payload.get("source_url") or "").strip()
    if raw_source and not claim["source_url"]:
        errors.append("Use a public HTTPS source link.")
    raw_expiry = (payload.get("expires_at") or "").strip()
    if raw_expiry and not claim["expires_at"]:
        errors.append("Use a valid expiration date.")
    if errors:
        raise ContractorCredentialError(errors)
    return claim


def contractor_credential_review_payload(
    payload: dict,
    action: str,
    existing_source_url: str = "",
) -> dict:
    if action not in CREDENTIAL_REVIEW_ACTIONS:
        raise ContractorCredentialError(["Unsupported credential review action."])
    raw_source = (payload.get("source_url") or existing_source_url or "").strip()
    source_url = normalized_credential_source_url(raw_source)
    expires_at = normalized_optional_date(payload.get("expires_at"))
    review_note = compact_spaces(payload.get("review_note"))
    errors: list[str] = []
    if raw_source and not source_url:
        errors.append("Use a public HTTPS source link.")
    if action == "verify" and not source_url:
        errors.append("Add the public source checked before confirming this record.")
    raw_expiry = (payload.get("expires_at") or "").strip()
    if raw_expiry and not expires_at:
        errors.append("Use a valid expiration date.")
    current_date = datetime.now(timezone.utc).date().isoformat()
    if action == "verify" and expires_at and expires_at < current_date:
        errors.append("An expired record cannot be marked source checked.")
    if len(review_note) > CREDENTIAL_REVIEW_NOTE_MAX_LENGTH:
        errors.append(
            f"Keep the review note under {CREDENTIAL_REVIEW_NOTE_MAX_LENGTH} characters."
        )
    if action in {"pending", "reject"} and not review_note:
        errors.append("Add a short review note for the contractor.")
    if errors:
        raise ContractorCredentialError(errors)
    return {
        "status": CREDENTIAL_REVIEW_ACTIONS[action],
        "source_url": source_url,
        "expires_at": expires_at or None,
        "review_note": review_note,
    }


def credential_is_current(credential, today: str | None = None) -> bool:
    if credential is None:
        return False
    status = credential.get("status") if isinstance(credential, dict) else credential["status"]
    expires_at = (
        credential.get("expires_at")
        if isinstance(credential, dict)
        else credential["expires_at"]
    )
    return status == "verified" and (
        not expires_at
        or str(expires_at)
        >= (today or datetime.now(timezone.utc).date().isoformat())
    )


def credential_response(credential, *, include_private: bool = False) -> dict:
    def value(key, default=""):
        if isinstance(credential, dict):
            return credential.get(key, default)
        try:
            return credential[key]
        except (IndexError, KeyError, TypeError):
            return default

    credential_type = value("credential_type")
    jurisdiction = value("jurisdiction")
    status = value("status")
    result = {
        "id": int(value("id", 0) or 0),
        "credential_type": credential_type,
        "credential_type_label": CREDENTIAL_TYPE_LABELS.get(
            credential_type, "Credential"
        ),
        "jurisdiction": jurisdiction,
        "jurisdiction_label": CREDENTIAL_JURISDICTION_LABELS.get(
            jurisdiction, jurisdiction or "Other"
        ),
        "status": status,
        "status_label": CREDENTIAL_STATUS_LABELS.get(status, "Awaiting review"),
        "checked_at": value("checked_at") or "",
        "expires_at": value("expires_at") or "",
        "source_url": normalized_credential_source_url(value("source_url")),
        "current": credential_is_current(credential),
    }
    if include_private:
        result.update(
            {
                "claimed_identifier": value("claimed_identifier") or "",
                "claimed_name": value("claimed_name") or "",
                "review_note": value("review_note") or "",
                "created_at": value("created_at") or "",
                "updated_at": value("updated_at") or "",
            }
        )
    return result


def public_credential_responses(credentials) -> list[dict]:
    return [
        credential_response(credential)
        for credential in credentials
        if credential_is_current(credential)
    ]
