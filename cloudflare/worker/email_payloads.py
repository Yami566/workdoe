from __future__ import annotations

import hashlib
import hmac
import html
import re
from urllib.parse import urlparse

DEFAULT_FROM_EMAIL = "no-reply@workdoe.com"
DEFAULT_PREFERENCES_URL = "https://workdoe.com/client/profile#bid-reminders"
DEFAULT_LEAD_ALERTS_URL = "https://workdoe.com/leads#saved-lead-alerts"
DEFAULT_MODERATION_URL = "https://workdoe.com/admin"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_PATTERN = re.compile(r"^\d{6}$")
JOB_PATH_PATTERN = re.compile(r"^/jobs/[1-9][0-9]*$")
ADMIN_PATH_PATTERN = re.compile(r"^/admin$")
SUPPORTED_EMAIL_TYPES = {
    "contractor-new-lead",
    "login-code",
    "moderation-digest",
    "operator-report-alert",
    "repeat-provider-invitation",
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


def require_workdoe_preferences_url(value: str | None) -> str:
    url = compact_spaces(value) or DEFAULT_PREFERENCES_URL
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"workdoe.com", "www.workdoe.com"}:
        raise EmailPayloadError("Reminder preferences URL must stay on workdoe.com.")
    if parsed.path != "/client/profile" or parsed.fragment != "bid-reminders":
        raise EmailPayloadError("Reminder preferences URL must point to Workdoe bid reminders.")
    return url


def require_workdoe_job_url(value: str | None) -> str:
    url = compact_spaces(value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"workdoe.com", "www.workdoe.com"}:
        raise EmailPayloadError("Project URL must stay on workdoe.com.")
    if not JOB_PATH_PATTERN.fullmatch(parsed.path) or parsed.query or parsed.fragment:
        raise EmailPayloadError("Project URL must point to one Workdoe project.")
    return url


def require_workdoe_lead_alerts_url(value: str | None) -> str:
    url = compact_spaces(value) or DEFAULT_LEAD_ALERTS_URL
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"workdoe.com", "www.workdoe.com"}:
        raise EmailPayloadError("Lead alert settings URL must stay on workdoe.com.")
    if parsed.path != "/leads" or parsed.fragment != "saved-lead-alerts" or parsed.query:
        raise EmailPayloadError("Lead alert settings URL must point to Workdoe lead alerts.")
    return url


def require_workdoe_moderation_url(value: str | None) -> str:
    url = compact_spaces(value) or DEFAULT_MODERATION_URL
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"workdoe.com", "www.workdoe.com"}:
        raise EmailPayloadError("Moderation URL must stay on workdoe.com.")
    if not ADMIN_PATH_PATTERN.fullmatch(parsed.path) or parsed.query or parsed.fragment:
        raise EmailPayloadError("Moderation URL must point to the Workdoe admin console.")
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


def stale_match_reminder_message(payload: dict, from_email: str) -> dict:
    job_title = clean_text(payload.get("job_title"), 120) or "your Workdoe lead"
    location = clean_text(payload.get("location"), 120) or "the DMV area"
    contractor_name = clean_text(payload.get("contractor_name"), 120) or "a contractor"
    preferences_url = require_workdoe_preferences_url(payload.get("preferences_url"))
    subject = f"Mini bid waiting: {job_title}"
    text = (
        f"{contractor_name} sent a mini bid for {job_title} in {location}. "
        "Sign in to Workdoe to review, approve, or reject the request.\n\n"
        f"Manage bid reminder emails: {preferences_url}"
    )
    html_body = (
        "<p>"
        f"{html.escape(contractor_name)} sent a mini bid for "
        f"<strong>{html.escape(job_title)}</strong> in {html.escape(location)}."
        "</p><p>Sign in to Workdoe to review, approve, or reject the request.</p>"
        f'<p><a href="{html.escape(preferences_url)}">Manage bid reminder emails</a></p>'
    )
    return message_shell(payload.get("to"), subject, text, html_body, from_email)


def repeat_provider_invitation_message(payload: dict, from_email: str) -> dict:
    job_title = clean_text(payload.get("job_title"), 120) or "a new Workdoe project"
    location = clean_text(payload.get("location"), 120) or "the DMV area"
    job_url = require_workdoe_job_url(payload.get("job_url"))
    subject = f"New Workdoe project invitation: {job_title}"
    text = (
        f"A prior Workdoe client invited you to send a fresh mini bid for {job_title} "
        f"in {location}. This is a new project, so prior pricing, messages, contact "
        f"details, and project access were not carried over. Review or pass: {job_url}"
    )
    html_body = (
        "<p>A prior Workdoe client invited you to send a fresh mini bid for "
        f"<strong>{html.escape(job_title)}</strong> in {html.escape(location)}.</p>"
        "<p>This is a new project, so prior pricing, messages, contact details, and "
        "project access were not carried over.</p>"
        f'<p><a href="{html.escape(job_url)}">Review or pass on Workdoe</a></p>'
    )
    return message_shell(payload.get("to"), subject, text, html_body, from_email)


def contractor_new_lead_message(payload: dict, from_email: str) -> dict:
    job_title = clean_text(payload.get("job_title"), 120) or "a new local project"
    service_name = clean_text(payload.get("service_name"), 120) or "your saved service"
    location = clean_text(payload.get("location"), 120) or "the DMV area"
    job_url = require_workdoe_job_url(payload.get("job_url"))
    settings_url = require_workdoe_lead_alerts_url(payload.get("settings_url"))
    subject = f"New matching Workdoe project: {job_title}"
    text = (
        f"A new {service_name} project matches your saved Workdoe services, area, "
        f"and lead view: {job_title} in {location}. Review the project and remaining "
        f"mini-bid slots: {job_url}\n\nManage matching project emails: {settings_url}"
    )
    html_body = (
        f"<p>A new {html.escape(service_name)} project matches your saved Workdoe "
        f"services, area, and lead view: <strong>{html.escape(job_title)}</strong> "
        f"in {html.escape(location)}.</p>"
        f'<p><a href="{html.escape(job_url)}">Review project and mini-bid slots</a></p>'
        f'<p><a href="{html.escape(settings_url)}">Manage matching project emails</a></p>'
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


def operator_report_alert_message(payload: dict, from_email: str, admin_email: str) -> dict:
    report_id = safe_int(payload.get("report_id"))
    target_type = clean_text(payload.get("target_type"), 24).lower()
    target_id = safe_int(payload.get("target_id"))
    if not report_id or target_type not in {"job", "message", "profile"} or not target_id:
        raise EmailPayloadError("Operator report alert must identify a valid report target.")
    moderation_url = require_workdoe_moderation_url(payload.get("moderation_url"))
    subject = "Workdoe moderation review needed"
    text = (
        f"A signed-in Workdoe account submitted report #{report_id} about a {target_type}. "
        "Review it in the moderation console. This alert intentionally omits report text, "
        f"account details, and project details: {moderation_url}"
    )
    html_body = (
        "<p>A signed-in Workdoe account submitted a moderation report.</p>"
        "<p>This alert intentionally omits report text, account details, and project details.</p>"
        f'<p><a href="{html.escape(moderation_url)}">Open the moderation console</a></p>'
    )
    return message_shell(
        payload.get("to") or admin_email,
        subject,
        text,
        html_body,
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
    if event_type == "stale-match-reminder":
        return stale_match_reminder_message(payload, from_email)
    if event_type == "repeat-provider-invitation":
        return repeat_provider_invitation_message(payload, from_email)
    if event_type == "contractor-new-lead":
        return contractor_new_lead_message(payload, from_email)
    if event_type == "moderation-digest":
        return moderation_digest_message(payload, from_email, admin_email)
    if event_type == "operator-report-alert":
        return operator_report_alert_message(payload, from_email, admin_email)
    raise EmailPayloadError("Unsupported email payload type.")


def email_audit_metadata(payload: dict, secret: str) -> dict:
    event_type = clean_text(payload.get("type") if isinstance(payload, dict) else "", 40)
    metadata = {"type": event_type or "unknown"}
    if not isinstance(payload, dict):
        return metadata
    recipient = normalize_email(payload.get("to"))
    if not recipient:
        return metadata
    metadata["recipient_present"] = True
    secret_bytes = str(secret or "").encode("utf-8")
    if len(secret_bytes) >= 32:
        metadata["recipient_hash"] = hmac.new(
            secret_bytes,
            f"email-audit:{recipient}".encode(),
            hashlib.sha256,
        ).hexdigest()
    return metadata


def email_send_result_summary(result) -> dict:
    values = result if isinstance(result, dict) else {
        key: getattr(result, key, None)
        for key in ("messageId", "delivered", "queued", "permanent_bounces")
    }
    summary = {}
    message_id = values.get("messageId")
    if message_id is not None:
        summary["messageId"] = clean_text(str(message_id), 160)
    for key in ("delivered", "queued"):
        value = values.get(key)
        if isinstance(value, (bool, int)):
            summary[key] = value
    bounces = values.get("permanent_bounces")
    if isinstance(bounces, (list, tuple, set)):
        summary["permanent_bounce_count"] = len(bounces)
    elif isinstance(bounces, int) and not isinstance(bounces, bool):
        summary["permanent_bounce_count"] = max(0, bounces)
    return summary or {"accepted": True}
