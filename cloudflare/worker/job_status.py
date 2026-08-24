from __future__ import annotations

JOB_STATUS_ACTIONS = {"close": "closed", "reopen": "open"}
JOB_STATUS_EVENTS = {"closed": "job-closed", "open": "job-reopened"}
PROJECT_CLOSE_REASONS = (
    {"value": "workdoe-match", "label": "Hired through Workdoe", "description": "A Workdoe contractor was selected for this project."},
    {"value": "hired-elsewhere", "label": "Hired elsewhere", "description": "The project moved forward outside Workdoe."},
    {"value": "plans-changed", "label": "Plans changed", "description": "The work is no longer moving forward right now."},
    {"value": "no-qualified-bid", "label": "No bid fit", "description": "The bids did not fit the scope, timing, or budget."},
    {"value": "scope-changed", "label": "Scope changed", "description": "The project needs to be rewritten or posted again."},
    {"value": "duplicate", "label": "Duplicate post", "description": "Another Workdoe post covers the same project."},
    {"value": "other", "label": "Other", "description": "Another reason best explains the close-out."},
)
LEAD_QUALITY_REASONS = (
    {"value": "insufficient-detail", "label": "Not enough detail", "description": "The scope is too thin to estimate responsibly."},
    {"value": "wrong-service", "label": "Wrong service", "description": "The project is filed under the wrong kind of work."},
    {"value": "outside-service-area", "label": "Outside service area", "description": "The project is not practical for the listed area."},
    {"value": "client-unresponsive", "label": "No client response", "description": "The consumer did not respond after the bid was sent."},
    {"value": "already-hired", "label": "Already hired", "description": "The project was no longer available when contact began."},
    {"value": "duplicate", "label": "Duplicate lead", "description": "The same project appears more than once."},
    {"value": "authorization-concern", "label": "Authorization concern", "description": "It is unclear whether the consumer can authorize the work."},
    {"value": "suspicious", "label": "Suspicious request", "description": "The lead may be fraudulent or unsafe."},
    {"value": "other", "label": "Other", "description": "Another quality issue applies."},
)
PROJECT_CLOSE_REASON_VALUES = frozenset(option["value"] for option in PROJECT_CLOSE_REASONS)
LEAD_QUALITY_REASON_VALUES = frozenset(option["value"] for option in LEAD_QUALITY_REASONS)
OUTCOME_NOTE_MAX_LENGTH = 300
MAX_OUTCOME_BODY_BYTES = 4 * 1024


class JobStatusError(ValueError):
    def __init__(self, message: str, status: int = 400, field: str = ""):
        self.status = status
        self.field = field
        super().__init__(message)


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def parse_job_status_path(path: str) -> tuple[int, str, str]:
    prefix = "/api/jobs/"
    if not path.startswith(prefix):
        raise JobStatusError("Unsupported job status route.", 404)
    parts = [part for part in path[len(prefix) :].split("/") if part]
    if len(parts) != 2:
        raise JobStatusError("Unsupported job status route.", 404)
    raw_id, action = parts
    if not raw_id.isdigit() or int(raw_id) < 1:
        raise JobStatusError("Unsupported job status route.", 404)
    if action not in JOB_STATUS_ACTIONS:
        raise JobStatusError("Unsupported job status route.", 404)
    return int(raw_id), action, JOB_STATUS_ACTIONS[action]


def can_update_job_status(user, job) -> bool:
    if not user or not job:
        return False
    if row_value(user, "status") != "active":
        return False
    return row_value(user, "role") == "client" and row_value(user, "id") == row_value(job, "client_id")


def job_status_event_type(status: str) -> str:
    return JOB_STATUS_EVENTS.get(status, "job-status-updated")


def job_status_response(job_id: int, status: str) -> dict:
    return {
        "ok": True,
        "job_id": job_id,
        "status": status,
        "url": f"/client/jobs/{job_id}",
    }


def _clean_value(payload: dict, key: str) -> str:
    return str(payload.get(key, "") or "").strip()


def _validated_note(payload: dict) -> str:
    note = _clean_value(payload, "note")
    if len(note) > OUTCOME_NOTE_MAX_LENGTH:
        raise JobStatusError(
            f"Keep the private note under {OUTCOME_NOTE_MAX_LENGTH} characters.",
            field="note",
        )
    return note


def validate_project_close_payload(payload: dict, has_approved_match: bool) -> dict:
    reason_code = _clean_value(payload, "reason_code")
    if reason_code not in PROJECT_CLOSE_REASON_VALUES:
        raise JobStatusError("Choose why this project is closing.", field="reason_code")
    if reason_code == "workdoe-match" and not has_approved_match:
        raise JobStatusError(
            "Approve a Workdoe bid before closing this as a Workdoe match.",
            field="reason_code",
        )
    return {"reason_code": reason_code, "note": _validated_note(payload)}


def parse_job_quality_feedback_path(path: str) -> int:
    prefix = "/api/jobs/"
    suffix = "/quality-feedback"
    if not path.startswith(prefix) or not path.endswith(suffix):
        raise JobStatusError("Unsupported lead feedback route.", 404)
    raw_id = path[len(prefix) : -len(suffix)].strip("/")
    if not raw_id.isdigit() or int(raw_id) < 1:
        raise JobStatusError("Unsupported lead feedback route.", 404)
    return int(raw_id)


def can_submit_lead_quality_feedback(user, job, match_request) -> bool:
    return bool(
        user
        and job
        and match_request
        and row_value(user, "status") == "active"
        and row_value(user, "role") == "contractor"
        and row_value(job, "status") != "hidden"
        and row_value(match_request, "contractor_id") == row_value(user, "id")
        and row_value(match_request, "job_id") == row_value(job, "id")
    )


def validate_lead_quality_payload(payload: dict) -> dict:
    reason_code = _clean_value(payload, "reason_code")
    if reason_code not in LEAD_QUALITY_REASON_VALUES:
        raise JobStatusError("Choose the lead-quality issue.", field="reason_code")
    return {"reason_code": reason_code, "note": _validated_note(payload)}


def project_close_reason_label(value: str | None) -> str:
    normalized = str(value or "").strip()
    for option in PROJECT_CLOSE_REASONS:
        if option["value"] == normalized:
            return option["label"]
    return "Closed"


def lead_quality_reason_label(value: str | None) -> str:
    normalized = str(value or "").strip()
    for option in LEAD_QUALITY_REASONS:
        if option["value"] == normalized:
            return option["label"]
    return "Lead feedback"
