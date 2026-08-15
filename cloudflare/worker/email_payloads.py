from __future__ import annotations

import html
import re
from urllib.parse import urlparse


DEFAULT_FROM_EMAIL = "no-reply@workdoe.com"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_PATTERN = re.compile(r"^\d{6}$")
SUPPORTED_EMAIL_TYPES = {
    "login-code",
    "moderation-digest",
    "password-reset",
    "stale-match-reminder",
}


class EmailPayloadError(ValueError):
    pass


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def normalize_email(value: str | None) -> str:
    return compact_spaces(value).lower()


def valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.match(value or ""))


def clean_subject(value: str) -> str:
    return compact_spaces(value).replace("\r", "").replace("\n", "")[:140]


def clean_text(value: str | None, maximum: int = 240) -> str:
    return compact_spaces(value)[:maximum]


def safe_int(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def require_recipient(value: str | None) -> str:
    email = normalize_email(value)
    if not valid_email(email):
        raise EmailPayloadError("Email recipient is missing or invalid.")
    return email


def clean_minutes(value, fallback: int, maximum: int = 60) -> int:
    try:
        minutes = int(value or fallback)
    except (TypeError, ValueError):
        minutes = fallback
    return min(max(minutes, 1), maximum)


def require_login_code(value: str | None) -> str:
    code = compact_spaces(value).replace(" ", "")
    if not CODE_PATTERN.match(code):
        raise EmailPayloadError("Login code must be a 6-digit code.")
    return code


def require_workdoe_url(value: str | None) -> str:
    url = compact_spaces(value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"workdoe.com", "www.workdoe.com"}:
        raise EmailPayloadError("Reset URL must stay on workdoe.com.")
    if not parsed.path.startswith("/reset-password/"):
        raise EmailPayloadError("Reset URL must point to a Workdoe reset route.")
    return url


def message_shell(to_email: str, subject: str, text: str, html_body: str, from_email: str) -> dict:
    return {
        "to": require_recipient(to_email),
        "from": require_recipient(from_email),
        "subject": clean_subject(subject),
        "text": text,
        "html": html_body,
    }


def login_code_message(payload: dict, from_email: str) -> dict:
    code = require_login_code(payload.get("code"))
    expires_minutes = clean_minutes(payload.get("expires_minutes"), 10, maximum=30)
    intent = clean_text(payload.get("intent"), 80) or "continue"
    subject = "Your Workdoe sign-in code"
    text = (
        f"Your Workdoe code is {code}. It expires in {expires_minutes} minutes. "
        f"Use it to {intent}. If you did not request this, you can ignore this email."
    )
    html_body = (
        "<p>Your Workdoe code is "
        f"<strong>{html.escape(code)}</strong>.</p>"
        f"<p>It expires in {expires_minutes} minutes. Use it to "
        f"{html.escape(intent)}.</p>"
        "<p>If you did not request this, you can ignore this email.</p>"
    )
    return message_shell(payload.get("to"), subject, text, html_body, from_email)


def password_reset_message(payload: dict, from_email: str) -> dict:
    reset_url = require_workdoe_url(payload.get("reset_url"))
    expires_minutes = clean_minutes(payload.get("expires_minutes"), 30, maximum=120)
    subject = "Reset your Workdoe password"
    text = (
        f"Reset your Workdoe password: {reset_url}\n\n"
        f"This link expires in {expires_minutes} minutes. "
        "If you did not request this, you can ignore this email."
    )
    html_body = (
        "<p>Reset your Workdoe password:</p>"
        f'<p><a href="{html.escape(reset_url)}">{html.escape(reset_url)}</a></p>'
        f"<p>This link expires in {expires_minutes} minutes. "
        "If you did not request this, you can ignore this email.</p>"
    )
    return message_shell(payload.get("to"), subject, text, html_body, from_email)


def stale_match_reminder_message(payload: dict, from_email: str) -> dict:
    job_title = clean_text(payload.get("job_title"), 120) or "your Workdoe lead"
    location = clean_text(payload.get("location"), 120) or "the DMV area"
    contractor_name = clean_text(payload.get("contractor_name"), 120) or "a contractor"
    subject = f"Mini bid waiting: {job_title}"
    text = (
        f"{contractor_name} sent a mini bid for {job_title} in {location}. "
        "Sign in to Workdoe to review, approve, or reject the request."
    )
    html_body = (
        "<p>"
        f"{html.escape(contractor_name)} sent a mini bid for "
        f"<strong>{html.escape(job_title)}</strong> in {html.escape(location)}."
        "</p><p>Sign in to Workdoe to review, approve, or reject the request.</p>"
    )
    return message_shell(payload.get("to"), subject, text, html_body, from_email)


def moderation_digest_message(payload: dict, from_email: str, admin_email: str) -> dict:
    summary = payload.get("summary") or {}
    if not isinstance(summary, dict):
        raise EmailPayloadError("Moderation digest summary must be an object.")
    metrics = {
        "Open reports": safe_int(summary.get("open_reports")),
        "Hidden job photos": safe_int(summary.get("hidden_job_photos")),
        "Hidden contractor photos": safe_int(summary.get("hidden_contractor_photos")),
        "Hidden messages": safe_int(summary.get("hidden_messages")),
        "Suspended users": safe_int(summary.get("suspended_users")),
    }
    text_lines = ["Workdoe moderation digest", ""]
    text_lines.extend(f"{label}: {value}" for label, value in metrics.items())
    html_items = "".join(
        f"<li><strong>{html.escape(label)}:</strong> {value}</li>"
        for label, value in metrics.items()
    )
    return message_shell(
        payload.get("to") or admin_email,
        "Workdoe moderation digest",
        "\n".join(text_lines),
        f"<p>Workdoe moderation digest</p><ul>{html_items}</ul>",
        from_email,
    )


def build_email_message(
    payload: dict,
    from_email: str = DEFAULT_FROM_EMAIL,
    admin_email: str = "",
) -> dict:
    if not isinstance(payload, dict):
        raise EmailPayloadError("Email payload must be an object.")
    event_type = payload.get("type")
    if event_type == "login-code":
        return login_code_message(payload, from_email)
    if event_type == "password-reset":
        return password_reset_message(payload, from_email)
    if event_type == "stale-match-reminder":
        return stale_match_reminder_message(payload, from_email)
    if event_type == "moderation-digest":
        return moderation_digest_message(payload, from_email, admin_email)
    raise EmailPayloadError("Unsupported email payload type.")
