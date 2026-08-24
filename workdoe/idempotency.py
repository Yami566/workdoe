from __future__ import annotations

import hashlib
import re
import uuid

IDEMPOTENCY_KEY_MIN_LENGTH = 20
IDEMPOTENCY_KEY_MAX_LENGTH = 128
IDEMPOTENCY_ACTION_MAX_LENGTH = 80
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")
IDEMPOTENCY_RESOURCE_TYPES = {"job", "message", "report", "job_photo", "contractor_photo"}


class IdempotencyError(ValueError):
    pass


def new_idempotency_key() -> str:
    return uuid.uuid4().hex


def normalize_idempotency_key(value, *, required: bool = False) -> str:
    key = str(value or "").strip()
    if not key:
        if required:
            raise IdempotencyError("A request key is required. Refresh and try again.")
        return ""
    if not IDEMPOTENCY_KEY_MIN_LENGTH <= len(key) <= IDEMPOTENCY_KEY_MAX_LENGTH:
        raise IdempotencyError("The request key is invalid. Refresh and try again.")
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
        raise IdempotencyError("The request key is invalid. Refresh and try again.")
    return key


def idempotency_key_hash(value) -> str:
    key = normalize_idempotency_key(value, required=True)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def idempotency_action(kind: str, target_id: int | None = None) -> str:
    action = str(kind or "").strip().lower()
    base_pattern = r"[a-z][a-z0-9-]*"
    if not action or not re.fullmatch(
        base_pattern if target_id is not None else rf"{base_pattern}(?::[1-9][0-9]*)?",
        action,
    ):
        raise IdempotencyError("The request action is invalid.")
    if target_id is not None:
        target = int(target_id)
        if target <= 0:
            raise IdempotencyError("The request target is invalid.")
        action = f"{action}:{target}"
    if len(action) > IDEMPOTENCY_ACTION_MAX_LENGTH:
        raise IdempotencyError("The request action is invalid.")
    return action


def idempotency_resource_type(value: str) -> str:
    resource_type = str(value or "").strip().lower()
    if resource_type not in IDEMPOTENCY_RESOURCE_TYPES:
        raise IdempotencyError("The request resource is invalid.")
    return resource_type
