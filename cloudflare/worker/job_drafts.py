from __future__ import annotations

import secrets

from email_code_auth import hash_identifier, parse_cookie_header


JOB_DRAFT_COOKIE_NAME = "workdoe_job_draft"
JOB_DRAFT_TTL_SECONDS = 24 * 60 * 60


def generate_job_draft_token() -> str:
    return secrets.token_urlsafe(32)


def job_draft_token_hash(token: str, secret: str) -> str:
    return hash_identifier(f"job-draft:{token}", secret)


def job_draft_token_from_cookie(cookie_header: str | None) -> str:
    return parse_cookie_header(cookie_header).get(JOB_DRAFT_COOKIE_NAME, "")


def job_draft_cookie(token: str) -> str:
    return (
        f"{JOB_DRAFT_COOKIE_NAME}={token}; Path=/; Max-Age={JOB_DRAFT_TTL_SECONDS}; "
        "HttpOnly; Secure; SameSite=Lax"
    )


def clear_job_draft_cookie() -> str:
    return f"{JOB_DRAFT_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
