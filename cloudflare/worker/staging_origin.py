from __future__ import annotations

import re
from urllib.parse import urlsplit

STAGING_ORIGIN = re.compile(
    r"https://(staging(?:-[a-z0-9](?:[a-z0-9-]{0,53}[a-z0-9])?)?\.workdoe\.com)"
)


def staging_hostname(public_url: object) -> str:
    match = STAGING_ORIGIN.fullmatch(public_url) if isinstance(public_url, str) else None
    return match[1] if match else ""


def staging_request_allowed(request_url: str, public_url: object, domain: object) -> bool:
    hostname = staging_hostname(public_url)
    if not hostname or domain != hostname:
        return False
    try:
        request = urlsplit(request_url)
    except ValueError:
        return False
    return request.scheme == "https" and request.netloc == hostname


def is_staging_environment(env) -> bool:
    return str(getattr(env, "WORKDOE_ENV", "production")).strip().lower() == "staging"
