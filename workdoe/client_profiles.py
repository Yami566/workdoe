from __future__ import annotations

import re


CLIENT_ACCOUNT_TYPES = (
    ("household", "Home or household"),
    ("small_business", "Small business"),
    ("property_manager", "Property manager"),
    ("community", "Community or nonprofit"),
)
CLIENT_NOTIFICATION_OPTIONS = (
    ("workdoe", "Workdoe inbox only"),
    ("email", "Email and Workdoe inbox"),
)
CLIENT_ACCOUNT_TYPE_VALUES = {value for value, _label in CLIENT_ACCOUNT_TYPES}
CLIENT_NOTIFICATION_VALUES = {value for value, _label in CLIENT_NOTIFICATION_OPTIONS}
CLIENT_ORGANIZATION_MAX_LENGTH = 120
CLIENT_PROFILE_NOTE_MAX_LENGTH = 400
SAVED_LOCATION_LABEL_MAX_LENGTH = 60
SAVED_LOCATION_CITY_MAX_LENGTH = 80
SAVED_LOCATION_LIMIT = 8
DMV_STATES = {"DC", "MD", "VA"}


class ClientProfileError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        self.field_errors = client_profile_field_errors(errors)
        super().__init__("; ".join(errors))


class SavedLocationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        self.field_errors = saved_location_field_errors(errors)
        super().__init__("; ".join(errors))


def row_value(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return getattr(row, key, default)


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def cleaned_client_profile_payload(payload) -> dict[str, str]:
    return {
        "organization_name": compact_spaces(payload.get("organization_name")),
        "account_type": compact_spaces(payload.get("account_type")).lower(),
        "notification_preference": compact_spaces(
            payload.get("notification_preference")
        ).lower(),
        "profile_note": (payload.get("profile_note") or "").strip(),
    }


def validate_client_profile_payload(form: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not form["organization_name"]:
        errors.append("Add a household or organization name.")
    elif len(form["organization_name"]) > CLIENT_ORGANIZATION_MAX_LENGTH:
        errors.append(
            f"Keep the household or organization name under {CLIENT_ORGANIZATION_MAX_LENGTH} characters."
        )
    if form["account_type"] not in CLIENT_ACCOUNT_TYPE_VALUES:
        errors.append("Choose the kind of consumer workspace this is.")
    if form["notification_preference"] not in CLIENT_NOTIFICATION_VALUES:
        errors.append("Choose where Workdoe should send bid reminders.")
    if len(form["profile_note"]) > CLIENT_PROFILE_NOTE_MAX_LENGTH:
        errors.append(
            f"Keep the private workspace note under {CLIENT_PROFILE_NOTE_MAX_LENGTH} characters."
        )
    return errors


def client_profile_field_errors(errors: list[str]) -> dict[str, list[str]]:
    field_errors: dict[str, list[str]] = {}
    for message in errors:
        if "household or organization name" in message:
            field = "organization_name"
        elif "consumer workspace" in message:
            field = "account_type"
        elif "bid reminders" in message:
            field = "notification_preference"
        elif "workspace note" in message:
            field = "profile_note"
        else:
            continue
        field_errors.setdefault(field, []).append(message)
    return field_errors


def client_profile_payload(payload) -> dict[str, str]:
    if not hasattr(payload, "get"):
        raise ClientProfileError(["Consumer profile payload must be an object."])
    form = cleaned_client_profile_payload(payload)
    errors = validate_client_profile_payload(form)
    if errors:
        raise ClientProfileError(errors)
    return form


def cleaned_saved_location_payload(payload) -> dict[str, str]:
    return {
        "label": compact_spaces(payload.get("label")),
        "city": compact_spaces(payload.get("city")),
        "state": compact_spaces(payload.get("state")).upper(),
        "zip_code": compact_spaces(payload.get("zip_code")),
    }


def validate_saved_location_payload(form: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not form["label"]:
        errors.append("Add a short name for this project area.")
    elif len(form["label"]) > SAVED_LOCATION_LABEL_MAX_LENGTH:
        errors.append(
            f"Keep the project area name under {SAVED_LOCATION_LABEL_MAX_LENGTH} characters."
        )
    if not form["city"]:
        errors.append("Add the city for this project area.")
    elif len(form["city"]) > SAVED_LOCATION_CITY_MAX_LENGTH:
        errors.append(
            f"Keep the project area city under {SAVED_LOCATION_CITY_MAX_LENGTH} characters."
        )
    if form["state"] not in DMV_STATES:
        errors.append("Choose DC, Maryland, or Virginia for this project area.")
    if not re.fullmatch(r"\d{5}", form["zip_code"]):
        errors.append("Use a 5-digit ZIP code for this project area.")
    return errors


def saved_location_field_errors(errors: list[str]) -> dict[str, list[str]]:
    field_errors: dict[str, list[str]] = {}
    for message in errors:
        if "short name" in message or "area name" in message:
            field = "label"
        elif "city" in message:
            field = "city"
        elif "DC, Maryland" in message:
            field = "state"
        elif "ZIP code" in message:
            field = "zip_code"
        else:
            continue
        field_errors.setdefault(field, []).append(message)
    return field_errors


def saved_location_payload(payload) -> dict[str, str]:
    if not hasattr(payload, "get"):
        raise SavedLocationError(["Saved project area payload must be an object."])
    form = cleaned_saved_location_payload(payload)
    errors = validate_saved_location_payload(form)
    if errors:
        raise SavedLocationError(errors)
    return form


def can_update_client_profile(user) -> bool:
    return bool(user) and row_value(user, "status") == "active" and row_value(
        user, "role"
    ) == "client"


def client_profile_response(profile) -> dict[str, str]:
    account_type = str(row_value(profile, "account_type", "household") or "household")
    notification_preference = str(
        row_value(profile, "notification_preference", "workdoe") or "workdoe"
    )
    email_reminder_consent_at = str(
        row_value(profile, "email_reminder_consent_at", "") or ""
    )
    if notification_preference == "email" and not email_reminder_consent_at:
        notification_preference = "workdoe"
    return {
        "organization_name": str(row_value(profile, "organization_name", "") or ""),
        "account_type": (
            account_type if account_type in CLIENT_ACCOUNT_TYPE_VALUES else "household"
        ),
        "notification_preference": (
            notification_preference
            if notification_preference in CLIENT_NOTIFICATION_VALUES
            else "workdoe"
        ),
        "email_reminder_consent_at": email_reminder_consent_at,
        "profile_note": str(row_value(profile, "profile_note", "") or ""),
        "updated_at": str(row_value(profile, "updated_at", "") or ""),
    }


def account_type_label(value: str | None) -> str:
    labels = dict(CLIENT_ACCOUNT_TYPES)
    return labels.get(str(value or ""), labels["household"])
