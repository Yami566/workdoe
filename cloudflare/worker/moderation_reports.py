from __future__ import annotations


REPORT_REASON_MAX_LENGTH = 500
MAX_REPORT_BODY_BYTES = 4096
REPORT_TARGET_TYPES = {"job", "message", "profile"}


class ModerationReportError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def parse_positive_int(value) -> int | None:
    try:
        parsed = int(value or "")
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def can_create_report(user) -> bool:
    return bool(user) and row_value(user, "status") == "active"


def report_target_query(target_type: str) -> str:
    if target_type == "job":
        return "SELECT 1 FROM jobs WHERE id = ? LIMIT 1"
    if target_type == "message":
        return "SELECT 1 FROM messages WHERE id = ? LIMIT 1"
    if target_type == "profile":
        return "SELECT 1 FROM contractor_profiles WHERE user_id = ? LIMIT 1"
    raise ModerationReportError(["Choose what to report and include a reason."])


def report_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ModerationReportError(["Report payload must be a JSON object."])
    target_type = compact_spaces(payload.get("target_type")).lower()
    target_id = parse_positive_int(payload.get("target_id"))
    reason = (payload.get("reason") or "").strip()
    if target_type not in REPORT_TARGET_TYPES or not target_id or not reason:
        raise ModerationReportError(["Choose what to report and include a reason."])
    if len(reason) > REPORT_REASON_MAX_LENGTH:
        raise ModerationReportError(["Keep report notes under 500 characters."])
    return {
        "target_type": target_type,
        "target_id": target_id,
        "reason": reason,
    }


def report_response(report_id: int | None, report: dict) -> dict:
    return {
        "ok": True,
        "report_id": report_id,
        "target_type": report["target_type"],
        "target_id": report["target_id"],
        "status": "open",
        "message": "Report sent to moderation.",
    }
