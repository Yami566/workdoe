from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from urllib.parse import urlparse

AUTH_PROVIDER = "workdoe_email_code"
SESSION_COOKIE_NAME = "workdoe_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
CHALLENGE_TTL_SECONDS = 10 * 60
MAX_CODE_ATTEMPTS = 5
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_PATTERN = re.compile(r"^\d{6}$")


class EmailCodeAuthError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def compact_spaces(value: str | None, maximum: int) -> str:
    return " ".join(str(value or "").strip().split())[:maximum]


def normalize_email(value: str | None) -> str:
    return compact_spaces(value, 254).lower()


def valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(value or ""))


def normalize_intent(value: str | None) -> str:
    return value if value in {"post-job", "find-work"} else "post-job"


def role_for_intent(intent: str) -> str:
    return "contractor" if intent == "find-work" else "client"


def fixed_account_role(existing_role: str | None, requested_role: str) -> str:
    if existing_role in {"client", "contractor", "admin"}:
        return str(existing_role)
    return requested_role if requested_role in {"client", "contractor"} else "client"


def normalize_code(value: str | None) -> str:
    return re.sub(r"[\s-]+", "", str(value or ""))


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def require_secret(secret: str | None) -> bytes:
    value = str(secret or "").encode("utf-8")
    if len(value) < 32:
        raise EmailCodeAuthError("Workdoe authentication is not configured.", 503)
    return value


def hash_code(code: str, secret: str) -> str:
    if not CODE_PATTERN.fullmatch(code or ""):
        raise EmailCodeAuthError("Sign-in code must contain six digits.")
    return hmac.new(require_secret(secret), f"otp:{code}".encode(), hashlib.sha256).hexdigest()


def hash_identifier(value: str | None, secret: str) -> str:
    normalized = str(value or "").strip().lower()
    return hmac.new(
        require_secret(secret),
        f"identifier:{normalized}".encode(),
        hashlib.sha256,
    ).hexdigest()


def tokens_match(left: str, right: str) -> bool:
    return hmac.compare_digest(str(left or ""), str(right or ""))


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def signed_token(payload: dict, secret: str) -> str:
    encoded = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(require_secret(secret), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_encode(signature)}"


def verified_token(token: str | None, secret: str, kind: str, now: int | None = None) -> dict:
    raw = str(token or "")
    if raw.count(".") != 1 or len(raw) > 2048:
        raise EmailCodeAuthError("Authentication token is invalid.", 401)
    encoded, supplied_signature = raw.split(".", 1)
    expected_signature = _encode(
        hmac.new(require_secret(secret), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    if not tokens_match(supplied_signature, expected_signature):
        raise EmailCodeAuthError("Authentication token is invalid.", 401)
    try:
        payload = json.loads(_decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EmailCodeAuthError("Authentication token is invalid.", 401) from exc
    current_time = int(time.time() if now is None else now)
    if not isinstance(payload, dict) or payload.get("kind") != kind:
        raise EmailCodeAuthError("Authentication token is invalid.", 401)
    if int(payload.get("exp") or 0) < current_time:
        raise EmailCodeAuthError("Authentication token expired.", 401)
    return payload


def challenge_token(code_id: int, email: str, secret: str, now: int | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    return signed_token(
        {
            "kind": "challenge",
            "code_id": int(code_id),
            "email": normalize_email(email),
            "iat": issued_at,
            "exp": issued_at + CHALLENGE_TTL_SECONDS,
        },
        secret,
    )


def session_token(user_id: int, secret: str, now: int | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    return signed_token(
        {
            "kind": "session",
            "user_id": int(user_id),
            "iat": issued_at,
            "exp": issued_at + SESSION_TTL_SECONDS,
        },
        secret,
    )


def parse_cookie_header(value: str | None) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for item in str(value or "").split(";"):
        if "=" not in item:
            continue
        name, cookie_value = item.split("=", 1)
        name = name.strip()
        if name:
            cookies[name] = cookie_value.strip()
    return cookies


def session_from_cookie(value: str | None, secret: str, now: int | None = None) -> dict:
    token = parse_cookie_header(value).get(SESSION_COOKIE_NAME, "")
    return verified_token(token, secret, "session", now=now)


def session_cookie(token: str) -> str:
    return (
        f"{SESSION_COOKIE_NAME}={token}; Path=/; Max-Age={SESSION_TTL_SECONDS}; "
        "HttpOnly; Secure; SameSite=Lax"
    )


def clear_session_cookie() -> str:
    return f"{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"


def safe_next_path(value: str | None, fallback: str = "/dashboard") -> str:
    candidate = str(value or "").strip()
    if not candidate or len(candidate) > 500 or not candidate.startswith("/"):
        return fallback
    if candidate.startswith("//") or "\\" in candidate:
        return fallback
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc or any(ord(character) < 32 for character in candidate):
        return fallback
    return candidate
