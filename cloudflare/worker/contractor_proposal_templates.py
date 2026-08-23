from __future__ import annotations

import re


PROPOSAL_TEMPLATE_LIMIT = 6
PROPOSAL_TEMPLATE_NAME_MAX_LENGTH = 60
PROPOSAL_TEMPLATE_DELETE_PATH_RE = re.compile(
    r"^/api/contractor/proposal-templates/([1-9][0-9]*)/delete$"
)


class ProposalTemplateError(ValueError):
    def __init__(
        self,
        errors: list[str],
        field_errors: dict[str, list[str]] | None = None,
    ):
        self.errors = errors
        self.field_errors = field_errors or {}
        super().__init__(" ".join(errors))


def row_value(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, default)


def compact_spaces(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def proposal_template_request_payload(payload) -> dict[str, str | int]:
    name = compact_spaces(payload.get("name"))
    raw_source_id = str(payload.get("source_match_request_id") or "").strip()
    errors: list[str] = []
    field_errors: dict[str, list[str]] = {}
    if not name:
        errors.append("Add a proposal template name.")
        field_errors["name"] = ["Add a proposal template name."]
    elif len(name) > PROPOSAL_TEMPLATE_NAME_MAX_LENGTH:
        message = (
            "Keep the proposal template name to "
            f"{PROPOSAL_TEMPLATE_NAME_MAX_LENGTH} characters."
        )
        errors.append(message)
        field_errors["name"] = [message]
    if not raw_source_id.isdigit() or int(raw_source_id) <= 0:
        errors.append("Choose one of your mini bids.")
        field_errors["source_match_request_id"] = ["Choose one of your mini bids."]
    if errors:
        raise ProposalTemplateError(errors, field_errors)
    return {"name": name, "source_match_request_id": int(raw_source_id)}


def proposal_template_values(name: str, bid) -> dict[str, str | int | None]:
    return {
        "name": name,
        "source_match_request_id": row_value(bid, "id"),
        "scope_note": str(row_value(bid, "scope_note", "") or ""),
        "timeline": compact_spaces(row_value(bid, "timeline", "")),
        "experience": str(row_value(bid, "experience", "") or ""),
        "questions": str(row_value(bid, "questions", "") or ""),
        "availability": compact_spaces(row_value(bid, "availability", "")),
    }


def proposal_template_response(row) -> dict[str, str | int | None]:
    return {
        "id": int(row_value(row, "id", 0) or 0),
        "name": str(row_value(row, "name", "") or ""),
        "source_match_request_id": row_value(row, "source_match_request_id"),
        "scope_note": str(row_value(row, "scope_note", "") or ""),
        "timeline": str(row_value(row, "timeline", "") or ""),
        "experience": str(row_value(row, "experience", "") or ""),
        "questions": str(row_value(row, "questions", "") or ""),
        "availability": str(row_value(row, "availability", "") or ""),
        "created_at": str(row_value(row, "created_at", "") or ""),
        "updated_at": str(row_value(row, "updated_at", "") or ""),
    }


def proposal_template_bid_form(row) -> dict[str, str]:
    return {
        "scope_note": str(row_value(row, "scope_note", "") or ""),
        "price_range": "",
        "timeline": str(row_value(row, "timeline", "") or ""),
        "experience": str(row_value(row, "experience", "") or ""),
        "questions": str(row_value(row, "questions", "") or ""),
        "availability": str(row_value(row, "availability", "") or ""),
    }


def parse_proposal_template_delete_path(path: str) -> int:
    match = PROPOSAL_TEMPLATE_DELETE_PATH_RE.fullmatch(path or "")
    if not match:
        raise ProposalTemplateError(["Unsupported proposal template route."])
    return int(match.group(1))
