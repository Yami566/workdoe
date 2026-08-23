from __future__ import annotations

BID_SCOPE_MIN_LENGTH = 20
BID_SCOPE_MAX_LENGTH = 800
BID_PRICE_MAX_LENGTH = 80
BID_TIMELINE_MAX_LENGTH = 120
BID_EXPERIENCE_MIN_LENGTH = 20
BID_EXPERIENCE_MAX_LENGTH = 800
BID_QUESTIONS_MAX_LENGTH = 500
BID_AVAILABILITY_MAX_LENGTH = 120
MAX_MATCH_REQUEST_BODY_BYTES = 8192


class MatchRequestError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        self.field_errors = match_request_field_errors(errors)
        super().__init__("; ".join(errors))


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def parse_match_request_job_id(path: str) -> int:
    prefix = "/api/jobs/"
    suffix = "/request"
    if not path.startswith(prefix) or not path.endswith(suffix):
        raise MatchRequestError(["Unsupported match request route."])
    raw_id = path[len(prefix) : -len(suffix)]
    if not raw_id.isdigit() or int(raw_id) < 1:
        raise MatchRequestError(["Unsupported match request route."])
    return int(raw_id)


def cleaned_match_request_payload(payload: dict) -> dict[str, str]:
    return {
        "scope_note": (payload.get("scope_note") or "").strip(),
        "price_range": compact_spaces(payload.get("price_range")),
        "timeline": compact_spaces(payload.get("timeline")),
        "experience": (payload.get("experience") or "").strip(),
        "questions": (payload.get("questions") or "").strip(),
        "availability": compact_spaces(payload.get("availability")),
    }


def validate_match_request_payload(form: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if len(form["scope_note"]) < BID_SCOPE_MIN_LENGTH:
        errors.append(f"Add at least {BID_SCOPE_MIN_LENGTH} characters about the scope.")
    elif len(form["scope_note"]) > BID_SCOPE_MAX_LENGTH:
        errors.append(f"Keep the scope note under {BID_SCOPE_MAX_LENGTH} characters.")
    if not form["price_range"]:
        errors.append("Add a price or range.")
    elif len(form["price_range"]) > BID_PRICE_MAX_LENGTH:
        errors.append(f"Keep the price range under {BID_PRICE_MAX_LENGTH} characters.")
    if not form["timeline"]:
        errors.append("Add a timeline.")
    elif len(form["timeline"]) > BID_TIMELINE_MAX_LENGTH:
        errors.append(f"Keep the timeline under {BID_TIMELINE_MAX_LENGTH} characters.")
    if len(form["experience"]) < BID_EXPERIENCE_MIN_LENGTH:
        errors.append(f"Add at least {BID_EXPERIENCE_MIN_LENGTH} characters about relevant experience.")
    elif len(form["experience"]) > BID_EXPERIENCE_MAX_LENGTH:
        errors.append(f"Keep relevant experience under {BID_EXPERIENCE_MAX_LENGTH} characters.")
    if len(form["questions"]) > BID_QUESTIONS_MAX_LENGTH:
        errors.append(f"Keep questions under {BID_QUESTIONS_MAX_LENGTH} characters.")
    if not form["availability"]:
        errors.append("Add availability.")
    elif len(form["availability"]) > BID_AVAILABILITY_MAX_LENGTH:
        errors.append(f"Keep availability under {BID_AVAILABILITY_MAX_LENGTH} characters.")
    return errors


def match_request_field_for_error(message: str) -> str:
    if "scope" in message:
        return "scope_note"
    if "price" in message:
        return "price_range"
    if "timeline" in message:
        return "timeline"
    if "experience" in message:
        return "experience"
    if "questions" in message:
        return "questions"
    if "availability" in message:
        return "availability"
    return ""


def match_request_field_errors(errors: list[str]) -> dict[str, list[str]]:
    field_errors: dict[str, list[str]] = {}
    for message in errors:
        field = match_request_field_for_error(message)
        if field:
            field_errors.setdefault(field, []).append(message)
    return field_errors


def match_request_payload(payload: dict) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise MatchRequestError(["Match request payload must be a JSON object."])
    form = cleaned_match_request_payload(payload)
    errors = validate_match_request_payload(form)
    if errors:
        raise MatchRequestError(errors)
    return form
