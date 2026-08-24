from __future__ import annotations

MAX_ONBOARDING_BODY_BYTES = 8192
ONBOARDING_ROLES = {"client", "contractor"}
ONBOARDING_TEXT_MAX_LENGTH = 120


class OnboardingError(ValueError):
    pass


def compact_spaces(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def normalize_email(value: str | None) -> str:
    return compact_spaces(value).lower()


def claim_email(claims: dict) -> str:
    for key in ("email", "primary_email", "primary_email_address"):
        email = normalize_email(claims.get(key))
        if email and "@" in email:
            return email
    raise OnboardingError("A verified Clerk email claim is required.")


def email_claim_verified(claims: dict) -> bool:
    value = claims.get("email_verified")
    return value in {None, True, "1", "true", "verified"}


def object_value(value, key: str, default=None):
    if value is None:
        return default
    getter = getattr(value, "get", None)
    if callable(getter):
        result = getter(key)
        return default if result is None else result
    try:
        result = value[key]
    except (KeyError, TypeError):
        return default
    return default if result is None else result


def claims_with_verified_clerk_email(claims: dict, user_data) -> dict:
    primary_id = str(object_value(user_data, "primary_email_address_id", "") or "")
    addresses = object_value(user_data, "email_addresses", []) or []
    selected = None
    for address in addresses:
        if primary_id and str(object_value(address, "id", "")) == primary_id:
            selected = address
            break
        if selected is None:
            selected = address
    email = normalize_email(object_value(selected, "email_address", ""))
    verification = object_value(selected, "verification", {}) or {}
    verified = object_value(verification, "status", "") == "verified"
    if not email or "@" not in email or not verified:
        raise OnboardingError("A verified Clerk email is required.")
    trusted_claims = dict(claims)
    trusted_claims["email"] = email
    trusted_claims["email_verified"] = True
    return trusted_claims


def onboarding_payload(claims: dict, body: dict) -> dict[str, str]:
    if not isinstance(body, dict):
        raise OnboardingError("Onboarding body must be a JSON object.")
    if not email_claim_verified(claims):
        raise OnboardingError("Clerk email claim is not verified.")

    role = compact_spaces(body.get("role")).lower()
    if role not in ONBOARDING_ROLES:
        raise OnboardingError("Role must be client or contractor.")

    display_name = compact_spaces(body.get("display_name"))[:ONBOARDING_TEXT_MAX_LENGTH]
    company_name = compact_spaces(body.get("company_name"))[:ONBOARDING_TEXT_MAX_LENGTH]
    if not display_name:
        display_name = compact_spaces(claims.get("name"))[:ONBOARDING_TEXT_MAX_LENGTH]
    if not display_name:
        display_name = claim_email(claims).split("@", 1)[0]
    if not company_name:
        company_name = display_name

    return {
        "email": claim_email(claims),
        "role": role,
        "display_name": display_name,
        "company_name": company_name,
    }
