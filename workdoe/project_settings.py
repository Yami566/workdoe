from __future__ import annotations

PROJECT_SETTINGS = (
    {
        "value": "house",
        "label": "House",
        "description": "A house or townhouse",
    },
    {
        "value": "apartment-condo",
        "label": "Apartment or condo",
        "description": "A private unit in a shared building",
    },
    {
        "value": "business-space",
        "label": "Business or office",
        "description": "A shop, office, or workspace",
    },
    {
        "value": "shared-building",
        "label": "Shared building area",
        "description": "A lobby, hallway, or shared room",
    },
    {
        "value": "outdoor-area",
        "label": "Outdoor area",
        "description": "A yard, patio, or other outdoor space",
    },
    {
        "value": "other",
        "label": "Other",
        "description": "Another project setting",
    },
)

PROJECT_SETTING_BY_VALUE = {
    setting["value"]: setting for setting in PROJECT_SETTINGS
}


def normalize_project_setting(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in PROJECT_SETTING_BY_VALUE else ""


def project_setting_label(value: str | None) -> str:
    setting = PROJECT_SETTING_BY_VALUE.get(normalize_project_setting(value))
    return setting["label"] if setting else "Not specified"
