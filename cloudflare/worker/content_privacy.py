from __future__ import annotations

import re
from collections.abc import Iterable

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(
    r"(?<![\w@])(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}(?!\w)"
)
_STREET_PATTERN = re.compile(
    r"\b(?:P\.?\s*O\.?\s+BOX\s*\d{1,8}|\d{1,5}\s+(?:[A-Z0-9.'-]+\s+){0,4}"
    r"(?:STREET|ST\.?|AVENUE|AVE\.?|ROAD|RD\.?|LANE|LN\.?|DRIVE|DR\.?|COURT|CT\.?|"
    r"BOULEVARD|BLVD\.?|PLACE|PL\.?|PARKWAY|PKWY\.?|TERRACE|TER\.?|CIRCLE|CIR\.?|"
    r"HIGHWAY|HWY\.?|TRAIL|TRL\.?))\b",
    re.IGNORECASE,
)


def contains_disallowed_personal_data(values: Iterable[object]) -> bool:
    """Detect common direct-contact and street-address disclosures.

    This intentionally stays small and deterministic. It is a prevention aid for
    the most common disclosures, not a claim that arbitrary free text is free
    of personal information.
    """

    for value in values:
        text = str(value or "")
        if _EMAIL_PATTERN.search(text) or _PHONE_PATTERN.search(text) or _STREET_PATTERN.search(text):
            return True
    return False


def personal_data_error(field_label: str) -> str:
    return (
        "Remove email addresses, phone numbers, or exact street addresses from "
        f"the {field_label}."
    )
