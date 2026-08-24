from __future__ import annotations

from collections.abc import Mapping

PROJECT_CLOSE_REASONS = (
    {
        "value": "workdoe-match",
        "label": "Hired through Workdoe",
        "description": "A Workdoe contractor was selected for this project.",
    },
    {
        "value": "hired-elsewhere",
        "label": "Hired elsewhere",
        "description": "The project moved forward outside Workdoe.",
    },
    {
        "value": "plans-changed",
        "label": "Plans changed",
        "description": "The work is no longer moving forward right now.",
    },
    {
        "value": "no-qualified-bid",
        "label": "No bid fit",
        "description": "The bids did not fit the scope, timing, or budget.",
    },
    {
        "value": "scope-changed",
        "label": "Scope changed",
        "description": "The project needs to be rewritten or posted again.",
    },
    {
        "value": "duplicate",
        "label": "Duplicate post",
        "description": "Another Workdoe post covers the same project.",
    },
    {
        "value": "other",
        "label": "Other",
        "description": "Another reason best explains the close-out.",
    },
)

LEAD_QUALITY_REASONS = (
    {
        "value": "insufficient-detail",
        "label": "Not enough detail",
        "description": "The scope is too thin to estimate responsibly.",
    },
    {
        "value": "wrong-service",
        "label": "Wrong service",
        "description": "The project is filed under the wrong kind of work.",
    },
    {
        "value": "outside-service-area",
        "label": "Outside service area",
        "description": "The project is not practical for the listed area.",
    },
    {
        "value": "client-unresponsive",
        "label": "No client response",
        "description": "The consumer did not respond after the bid was sent.",
    },
    {
        "value": "already-hired",
        "label": "Already hired",
        "description": "The project was no longer available when contact began.",
    },
    {
        "value": "duplicate",
        "label": "Duplicate lead",
        "description": "The same project appears more than once.",
    },
    {
        "value": "authorization-concern",
        "label": "Authorization concern",
        "description": "It is unclear whether the consumer can authorize the work.",
    },
    {
        "value": "suspicious",
        "label": "Suspicious request",
        "description": "The lead may be fraudulent or unsafe.",
    },
    {
        "value": "other",
        "label": "Other",
        "description": "Another quality issue applies.",
    },
)

PROJECT_CLOSE_REASON_VALUES = frozenset(
    option["value"] for option in PROJECT_CLOSE_REASONS
)
LEAD_QUALITY_REASON_VALUES = frozenset(
    option["value"] for option in LEAD_QUALITY_REASONS
)
OUTCOME_NOTE_MAX_LENGTH = 300


class JobOutcomeError(ValueError):
    def __init__(self, message: str, *, field: str = ""):
        self.field = field
        super().__init__(message)


def _clean_value(payload: Mapping, key: str) -> str:
    return str(payload.get(key, "") or "").strip()


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


def _validated_note(payload: Mapping) -> str:
    note = _clean_value(payload, "note")
    if len(note) > OUTCOME_NOTE_MAX_LENGTH:
        raise JobOutcomeError(
            f"Keep the private note under {OUTCOME_NOTE_MAX_LENGTH} characters.",
            field="note",
        )
    return note


def validate_project_close_payload(
    payload: Mapping,
    *,
    has_approved_match: bool,
) -> dict[str, str]:
    reason_code = _clean_value(payload, "reason_code")
    if reason_code not in PROJECT_CLOSE_REASON_VALUES:
        raise JobOutcomeError("Choose why this project is closing.", field="reason_code")
    if reason_code == "workdoe-match" and not has_approved_match:
        raise JobOutcomeError(
            "Approve a Workdoe bid before closing this as a Workdoe match.",
            field="reason_code",
        )
    return {"reason_code": reason_code, "note": _validated_note(payload)}


def validate_lead_quality_payload(payload: Mapping) -> dict[str, str]:
    reason_code = _clean_value(payload, "reason_code")
    if reason_code not in LEAD_QUALITY_REASON_VALUES:
        raise JobOutcomeError("Choose the lead-quality issue.", field="reason_code")
    return {"reason_code": reason_code, "note": _validated_note(payload)}
