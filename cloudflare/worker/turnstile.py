from __future__ import annotations

import uuid


TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TOKEN_MAX_LENGTH = 2048


class TurnstileError(ValueError):
    pass


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def turnstile_token_from_payload(payload: dict) -> str:
    token = compact_spaces(
        payload.get("turnstile_token") or payload.get("cf-turnstile-response")
        if isinstance(payload, dict)
        else ""
    )
    if not token:
        raise TurnstileError("Turnstile token is required.")
    if len(token) > TURNSTILE_TOKEN_MAX_LENGTH:
        raise TurnstileError("Turnstile token is too long.")
    return token


def remote_ip_from_headers(headers) -> str:
    for header in ("CF-Connecting-IP", "X-Forwarded-For"):
        getter = getattr(headers, "get", None)
        value = getter(header) if callable(getter) else None
        if value:
            return compact_spaces(str(value).split(",", 1)[0])
    return ""


def siteverify_payload(
    secret: str,
    token: str,
    remoteip: str = "",
    idempotency_key: str = "",
) -> dict[str, str]:
    if not compact_spaces(secret):
        raise TurnstileError("Turnstile secret key is required.")
    payload = {
        "secret": secret,
        "response": token,
        "idempotency_key": idempotency_key or str(uuid.uuid4()),
    }
    if remoteip:
        payload["remoteip"] = remoteip
    return payload


def turnstile_result_allowed(result: dict, allowed_hosts: set[str]) -> bool:
    if not isinstance(result, dict) or result.get("success") is not True:
        return False
    hostname = compact_spaces(result.get("hostname")).lower()
    return not hostname or hostname in allowed_hosts
