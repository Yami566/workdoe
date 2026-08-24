from __future__ import annotations

import re

REVIEW_DIMENSIONS = (
    ("communication", "Communication"),
    ("scope_accuracy", "Scope accuracy"),
    ("timeliness", "Timeliness"),
    ("work_outcome", "Work outcome"),
)
REVIEW_RATING_OPTIONS = (
    ("met", "Met expectations"),
    ("mixed", "Mixed"),
    ("concern", "Needs follow-up"),
    ("not_applicable", "Not applicable"),
)
WOULD_WORK_AGAIN_OPTIONS = (
    ("yes", "Yes"),
    ("unsure", "Not sure"),
    ("no", "No"),
)
REVIEW_RATING_LABELS = dict(REVIEW_RATING_OPTIONS)
WOULD_WORK_AGAIN_LABELS = dict(WOULD_WORK_AGAIN_OPTIONS)
REVIEW_COMMENT_MAX_LENGTH = 700
REVIEW_RESPONSE_MAX_LENGTH = 500
REVIEW_REPORT_MAX_LENGTH = 500
MAX_MATCH_REVIEW_BODY_BYTES = 8_192
MATCH_REVIEW_CREATE_RE = re.compile(
    r"^/api/match-requests/([1-9][0-9]*)/review/?$"
)
MATCH_REVIEW_ACTION_RE = re.compile(
    r"^/api/reviews/([1-9][0-9]*)/(response|report)/?$"
)


class MatchReviewError(ValueError):
    def __init__(self, message: str, status: int = 400):
        self.status = status
        super().__init__(message)


def parse_match_review_create_path(path: str) -> int:
    match = MATCH_REVIEW_CREATE_RE.match(path or "")
    if not match:
        raise MatchReviewError("Unsupported completed-work feedback route.", 404)
    return int(match.group(1))


def parse_match_review_action_path(path: str) -> tuple[int, str]:
    match = MATCH_REVIEW_ACTION_RE.match(path or "")
    if not match:
        raise MatchReviewError("Unsupported completed-work feedback route.", 404)
    return int(match.group(1)), match.group(2)


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def compact_spaces(value) -> str:
    return " ".join(str(value or "").split())


def review_participant_role(user, match) -> str:
    if not user or row_value(user, "status") != "active":
        return ""
    user_id = int(row_value(user, "id", 0) or 0)
    if row_value(user, "role") == "client" and user_id == int(
        row_value(match, "client_id", 0) or 0
    ):
        return "client"
    if row_value(user, "role") == "contractor" and user_id == int(
        row_value(match, "contractor_id", 0) or 0
    ):
        return "contractor"
    return ""


def validate_review_eligibility(user, match, existing_review=None) -> str:
    if not match:
        raise MatchReviewError("Completed Workdoe match not found.", 404)
    role = review_participant_role(user, match)
    if not role:
        raise MatchReviewError("Only match participants can leave feedback.", 403)
    if row_value(match, "match_status", row_value(match, "status")) != "approved":
        raise MatchReviewError("Feedback requires an approved Workdoe match.", 409)
    if not row_value(match, "verified_at"):
        raise MatchReviewError(
            "Both participants must confirm completion before leaving feedback.", 409
        )
    if existing_review:
        raise MatchReviewError("You already left feedback for this project.", 409)
    return role


def review_subject_id(role: str, match) -> int:
    key = "contractor_id" if role == "client" else "client_id"
    return int(row_value(match, key, 0) or 0)


def validate_review_payload(payload) -> dict:
    values = {}
    allowed_ratings = set(REVIEW_RATING_LABELS)
    for key, label in REVIEW_DIMENSIONS:
        value = compact_spaces(payload.get(key)).lower()
        if value not in allowed_ratings:
            raise MatchReviewError(f"Choose a {label.lower()} response.")
        values[key] = value
    would_work_again = compact_spaces(payload.get("would_work_again")).lower()
    if would_work_again not in WOULD_WORK_AGAIN_LABELS:
        raise MatchReviewError("Choose whether you would work together again.")
    comment = compact_spaces(payload.get("comment"))
    if len(comment) > REVIEW_COMMENT_MAX_LENGTH:
        raise MatchReviewError(
            f"Keep feedback under {REVIEW_COMMENT_MAX_LENGTH} characters."
        )
    values.update(
        {"would_work_again": would_work_again, "comment": comment}
    )
    return values


def validate_review_response(user, review, response) -> str:
    if not review:
        raise MatchReviewError("Feedback not found.", 404)
    if row_value(user, "status") != "active" or int(
        row_value(user, "id", 0) or 0
    ) != int(row_value(review, "subject_id", 0) or 0):
        raise MatchReviewError("Only the feedback recipient can respond.", 403)
    if row_value(review, "is_hidden"):
        raise MatchReviewError("Hidden feedback cannot receive a response.", 409)
    if row_value(review, "response"):
        raise MatchReviewError("A response is already recorded.", 409)
    value = compact_spaces(response)
    if not value:
        raise MatchReviewError("Add a short response.")
    if len(value) > REVIEW_RESPONSE_MAX_LENGTH:
        raise MatchReviewError(
            f"Keep the response under {REVIEW_RESPONSE_MAX_LENGTH} characters."
        )
    return value


def validate_review_report(user, review, reason) -> str:
    if not review:
        raise MatchReviewError("Feedback not found.", 404)
    user_id = int(row_value(user, "id", 0) or 0)
    if row_value(user, "status") != "active" or user_id not in {
        int(row_value(review, "reviewer_id", 0) or 0),
        int(row_value(review, "subject_id", 0) or 0),
    }:
        raise MatchReviewError("Only review participants can report this feedback.", 403)
    value = compact_spaces(reason)
    if not value:
        raise MatchReviewError("Add a reason for moderation review.")
    if len(value) > REVIEW_REPORT_MAX_LENGTH:
        raise MatchReviewError(
            f"Keep the report under {REVIEW_REPORT_MAX_LENGTH} characters."
        )
    return value


def review_response(review, include_private: bool = False) -> dict:
    payload = {
        "id": int(row_value(review, "id", 0) or 0),
        "match_request_id": int(row_value(review, "match_request_id", 0) or 0),
        "reviewer_role": str(row_value(review, "reviewer_role", "") or ""),
        "communication": str(row_value(review, "communication", "") or ""),
        "scope_accuracy": str(row_value(review, "scope_accuracy", "") or ""),
        "timeliness": str(row_value(review, "timeliness", "") or ""),
        "work_outcome": str(row_value(review, "work_outcome", "") or ""),
        "would_work_again": str(
            row_value(review, "would_work_again", "") or ""
        ),
        "comment": str(row_value(review, "comment", "") or ""),
        "response": str(row_value(review, "response", "") or ""),
        "created_at": str(row_value(review, "created_at", "") or ""),
        "response_at": str(row_value(review, "response_at", "") or ""),
        "verified_project": bool(row_value(review, "verified_at")),
        "is_hidden": bool(row_value(review, "is_hidden")),
    }
    for key, _label in REVIEW_DIMENSIONS:
        payload[f"{key}_label"] = REVIEW_RATING_LABELS.get(payload[key], "Feedback")
    payload["would_work_again_label"] = WOULD_WORK_AGAIN_LABELS.get(
        payload["would_work_again"], "Not stated"
    )
    if include_private:
        payload.update(
            {
                "reviewer_id": int(row_value(review, "reviewer_id", 0) or 0),
                "subject_id": int(row_value(review, "subject_id", 0) or 0),
            }
        )
    return payload
