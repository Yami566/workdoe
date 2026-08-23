from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Mapping

DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 5 * 60
SYNCABLE_USER_EVENTS = {"user.created", "user.updated", "user.deleted"}


class SvixVerificationError(ValueError):
    pass


def header_value(headers: Mapping[str, str] | object, *names: str) -> str:
    lowered = {name.lower() for name in names}
    if hasattr(headers, "get"):
        for name in names:
            value = headers.get(name)  # type: ignore[attr-defined]
            if value:
                return str(value)
    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if key.lower() in lowered and value:
                return str(value)
    return ""


def signing_secret_bytes(secret: str) -> bytes:
    if not secret.startswith("whsec_"):
        raise SvixVerificationError("Webhook signing secret must start with whsec_.")
    encoded = secret.removeprefix("whsec_")
    padded = encoded + ("=" * (-len(encoded) % 4))
    try:
        return base64.b64decode(padded.encode("ascii"), validate=True)
    except Exception as exc:
        raise SvixVerificationError("Webhook signing secret is not valid base64.") from exc


def svix_signature(
    *,
    secret: str,
    message_id: str,
    timestamp: str,
    raw_body: str | bytes,
) -> str:
    body_bytes = raw_body if isinstance(raw_body, bytes) else raw_body.encode("utf-8")
    signed_content = b".".join(
        [
            message_id.encode("utf-8"),
            timestamp.encode("utf-8"),
            body_bytes,
        ]
    )
    digest = hmac.new(signing_secret_bytes(secret), signed_content, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_svix_signature(
    *,
    secret: str,
    headers: Mapping[str, str] | object,
    raw_body: str | bytes,
    now: int | None = None,
    tolerance_seconds: int = DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
) -> dict:
    message_id = header_value(headers, "svix-id", "webhook-id")
    timestamp = header_value(headers, "svix-timestamp", "webhook-timestamp")
    signature_header = header_value(headers, "svix-signature", "webhook-signature")
    if not message_id or not timestamp or not signature_header:
        raise SvixVerificationError("Missing required Svix webhook signature headers.")

    try:
        timestamp_int = int(timestamp)
    except ValueError as exc:
        raise SvixVerificationError("Webhook timestamp is invalid.") from exc
    now_int = int(time.time() if now is None else now)
    if abs(now_int - timestamp_int) > tolerance_seconds:
        raise SvixVerificationError("Webhook timestamp is outside the allowed tolerance.")

    expected = svix_signature(
        secret=secret,
        message_id=message_id,
        timestamp=timestamp,
        raw_body=raw_body,
    )
    signatures = [
        part.split(",", 1)[1]
        for part in signature_header.split()
        if part.startswith("v1,") and len(part.split(",", 1)) == 2
    ]
    if not signatures:
        raise SvixVerificationError("Webhook signature header has no v1 signatures.")
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise SvixVerificationError("Webhook signature does not match.")

    body_text = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body
    try:
        event = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise SvixVerificationError("Webhook payload is not valid JSON.") from exc
    if event.get("object") != "event" or not event.get("type"):
        raise SvixVerificationError("Webhook payload is not a Clerk event.")
    return event


def primary_email_from_clerk_user(user_data: dict) -> tuple[str, bool]:
    primary_id = user_data.get("primary_email_address_id")
    addresses = user_data.get("email_addresses") or []
    selected = None
    if primary_id:
        selected = next((item for item in addresses if item.get("id") == primary_id), None)
    if selected is None and addresses:
        selected = addresses[0]
    if not selected:
        return "", False
    email = str(selected.get("email_address") or "").strip().lower()
    verification = selected.get("verification") or {}
    verified = verification.get("status") == "verified"
    return email, verified


def clerk_user_status(event_type: str, user_data: dict) -> str:
    if event_type == "user.deleted":
        return "suspended"
    if any(user_data.get(flag) is True for flag in ("banned", "locked", "disabled")):
        return "suspended"
    return "active"


def clerk_user_sync_payload(event: dict) -> dict:
    event_type = str(event.get("type") or "")
    user_data = event.get("data") or {}
    clerk_user_id = str(user_data.get("id") or "")
    if event_type not in SYNCABLE_USER_EVENTS or not clerk_user_id:
        return {
            "syncable": False,
            "event_type": event_type,
            "clerk_user_id": clerk_user_id,
            "reason": "unsupported-event",
        }

    email, email_verified = primary_email_from_clerk_user(user_data)
    return {
        "syncable": True,
        "event_type": event_type,
        "clerk_user_id": clerk_user_id,
        "email": email,
        "email_verified": int(email_verified),
        "status": clerk_user_status(event_type, user_data),
    }
