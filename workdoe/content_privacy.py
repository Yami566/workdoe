from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from unicodedata import category, normalize

_DASH_TRANSLATION = str.maketrans("\u2010\u2011\u2012\u2013\u2014\u2212", "------")
LOCALITY_NAME_ERROR = "Enter only the city or town name, without a street address or contact details."
PROJECT_SEARCH_INPUT_HINT = "Search by project, city, or ZIP. Leave out contact details and street addresses."
PUBLIC_PROJECT_PRIVACY_LOOKAHEAD = 16
PUBLIC_PROJECT_TEXT_FIELDS = (
    "title", "category", "city", "state", "desired_date", "service_slug", "service_group_slug",
)
_STREET_SUFFIXES = (
    "street", "st", "avenue", "ave", "road", "rd", "lane", "ln", "drive", "dr", "court", "ct",
    "boulevard", "blvd", "place", "pl", "parkway", "pkwy", "terrace", "ter", "circle", "cir",
    "highway", "hwy", "trail", "trl",
)
# HTML patterns use Unicode-sets regex syntax and do not accept flag arguments.
_BROWSER_STREET_SUFFIXES = "|".join("".join(f"[{char}{char.upper()}]" for char in suffix) for suffix in _STREET_SUFFIXES)
PROJECT_SEARCH_INPUT_PATTERN = (
    r"(?![\s\S]*(?:[@\uFF20]|(?:[0-9][\s.\(\)\+\-\u2010-\u2014\u2212]*){9}[0-9]"
    r"|\b(?:[Pp]\.?\s*[Oo]\.?\s+[Bb][Oo][Xx]\s*[0-9]+"
    r"|[0-9]{1,5}\s+(?:[A-Za-z0-9.'\-\u2010-\u2014\u2212]+\s+){0,4}(?:"
    + _BROWSER_STREET_SUFFIXES
    + r"))\b))[\s\S]*"
)
# Look for common SMTPUTF8 spellings too; this is not a mailbox validator.
_EMAIL_PATTERN = re.compile(
    r"(?<![\w.%+-])[\w.%+-]+@(?:[\w-]+\.)+(?:xn--[a-z0-9-]+|[^\W\d_]{2,})\b",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(
    r"(?<![\w@])(?:\+?1[ .-]?)?(?:\d{3}[ .-]\d{3}[ .-]\d{4}"
    r"|\(\d{3}\)[ .-]?\d{3}[ .-]?\d{4}|[2-9]\d{2}[2-9]\d{6})(?!\w)"
)
_STREET_PATTERN = re.compile(
    r"\b(?:P\.?\s*O\.?\s+BOX\s*\d{1,8}|\d{1,5}\s+(?:[A-Z0-9.'-]+\s+){0,4}"
    rf"(?:{'|'.join(_STREET_SUFFIXES)}))\b",
    re.IGNORECASE,
)


def _contains_contact_pattern(text: str) -> bool:
    return bool(_EMAIL_PATTERN.search(text) or _PHONE_PATTERN.search(text) or _STREET_PATTERN.search(text))


def contains_disallowed_personal_data(values: Iterable[object]) -> bool:
    """Detect common direct-contact and street-address disclosures.

    This intentionally stays small and deterministic. It is a prevention aid for
    the most common disclosures, not a claim that arbitrary free text is free
    of personal information.
    """

    for value in values:
        text = normalize("NFKC", str(value or "")).translate(_DASH_TRANSLATION)
        if _contains_contact_pattern(text):
            return True
        if not text.isascii():
            # Compare both interpretations; retain the original text for display and storage.
            joined = "".join(char for char in text if category(char) != "Cf")
            if joined != text and (
                _contains_contact_pattern(joined)
                or _contains_contact_pattern("".join(" " if category(char) == "Cf" else char for char in text))
            ):
                return True
    return False


def personal_data_error(field_label: str) -> str:
    return (
        "Remove email addresses, phone numbers, or exact street addresses from "
        f"the {field_label}."
    )


def participant_message_text(body: str) -> str:
    if contains_disallowed_personal_data((body,)):
        return "Message withheld because it may contain private contact or address details."
    return body


def public_contractor_profile_text(profile: Mapping[str, object]) -> dict[str, str]:
    # Old and imported rows may predate current profile validation.
    def visible(field: str, fallback: str) -> str:
        value = profile.get(field)
        if isinstance(value, str) and value.strip() and not contains_disallowed_personal_data((value,)):
            return value
        return fallback

    return {
        "business_name": visible("business_name", "Workdoe contractor"),
        "trades": visible("trades", ""),
        "service_area": visible("service_area", "DMV area"),
        "intro": visible("intro", "This contractor is still completing their profile."),
    }


def public_project_visible(row) -> bool:
    def value(field):
        try:
            return row[field]
        except (IndexError, KeyError, TypeError):
            return getattr(row, field, None)

    return not contains_disallowed_personal_data(value(field) for field in PUBLIC_PROJECT_TEXT_FIELDS)


def public_project_page(rows: list, limit: int) -> tuple[list, int]:
    # Cursor offsets are positions in the SQL result, not the displayed count.
    visible = []
    for index, row in enumerate(rows):
        if not public_project_visible(row):
            continue
        if len(visible) == limit:
            return [*visible, row], index
        visible.append(row)
    return visible, len(rows)


_BID_TERM_WITHHELD = "Withheld for privacy."
_SHARED_PROJECT_FALLBACKS = {
    "title": "Project",
    "job_title": "Project",
    "project_title": "Project",
    "description": "Brief withheld.",
    "category": "General work",
    "city": "Area withheld",
    "state": "DMV",
    "desired_date": "",
    "service_group_slug": "",
    "service_slug": "",
    "project_setting": "",
    "close_reason": "",
    "scope_note": _BID_TERM_WITHHELD,
    "price_range": _BID_TERM_WITHHELD,
    "timeline": _BID_TERM_WITHHELD,
    "experience": _BID_TERM_WITHHELD,
    "questions": _BID_TERM_WITHHELD,
    "availability": _BID_TERM_WITHHELD,
}


def shared_project_record(row) -> dict:
    """Build a read copy without flagged project or bid text."""
    record = dict(row)
    for field, fallback in _SHARED_PROJECT_FALLBACKS.items():
        if field in record and contains_disallowed_personal_data((record[field],)):
            record[field] = fallback
    return record


def cleaned_locality_input(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def cleaned_zip_input(value: object) -> str:
    text = value.strip() if isinstance(value, str) else ""
    return text[:5] if re.fullmatch(r"[0-9]{5}(?:-[0-9]{4})?", text) else ""


def cleaned_project_search(value: str, limit: int) -> str:
    text = " ".join(value.split())
    normalized = normalize("NFKC", text)
    if "@" in normalized or contains_disallowed_personal_data((normalized,)):
        return ""
    return text[:limit]


def is_locality_name(value: str) -> bool:
    text = normalize("NFKC", value).translate(_DASH_TRANSLATION)
    return any(char.isalpha() for char in text) and all(
        char.isalpha() or category(char).startswith("M") or char in " .'-\u2019"
        for char in text
    )
